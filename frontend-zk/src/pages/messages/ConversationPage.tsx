import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  getMessages,
  sendMessage as apiSendMessage,
  fetchPeerPrekeys,
  listConversations,
  type MessageResponse,
  type PrekeyBundleResponse,
} from "../../api/messaging";
import { ChatBubble } from "../../components/ChatBubble";
import { ChatInput } from "../../components/ChatInput";
import { useAuth } from "../../contexts/AuthContext";
import { useMessagingStream, type IncomingMessage } from "../../hooks/useMessagingStream";
import { initiateX3DH, respondX3DH, type PeerBundle } from "../../crypto/x3dh";
import {
  initSender,
  initReceiver,
  ratchetEncrypt,
  ratchetDecrypt,
  headerToBase64,
  headerFromBase64,
  x3dhHeaderToBase64,
  x3dhHeaderFromBase64,
  type RatchetState,
} from "../../crypto/doubleratchet";
import { deriveSignedPrekey, hexToBytes } from "../../crypto/keys";
import { saveSession, loadSession } from "../../crypto/sessionStore";

interface Props {
  conversationId: string;
}

interface DecryptedMessage {
  id: string;
  text: string;
  senderPubkey: string;
  isMine: boolean;
  timestamp: string;
  decryptionFailed?: boolean;
}

/**
 * Convert server prekey bundle response to the PeerBundle format X3DH expects.
 */
function toPeerBundle(resp: PrekeyBundleResponse): PeerBundle {
  return {
    identityPubkey: resp.identity_pubkey,
    identityX25519Pub: resp.identity_x25519_pub,
    signedPrekeyPub: resp.signed_prekey_pub,
    signedPrekeySig: resp.signed_prekey_sig,
    signedPrekeyId: resp.signed_prekey_id,
    oneTimePrekey: resp.one_time_prekey,
  };
}

export function ConversationPage({ conversationId }: Props) {
  const { publicKeyHex, publicKey, privateKey } = useAuth();
  const [messages, setMessages] = useState<DecryptedMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [cryptoReady, setCryptoReady] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Mutable ref for ratchet state (avoids stale closures)
  const ratchetRef = useRef<RatchetState | null>(null);
  // Track the peer pubkey for this conversation
  const peerPubkeyRef = useRef<string | null>(null);
  // Track the peer's SPK index (needed for respondX3DH)
  const peerSpkIndexRef = useRef<number>(0);

  // Load ratchet state from sessionStorage on mount
  useEffect(() => {
    const saved = loadSession(conversationId);
    if (saved) {
      ratchetRef.current = saved;
      setCryptoReady(true);
    }
  }, [conversationId]);

  // Decrypt a single message using the ratchet
  const decryptMessage = useCallback(
    async (msg: MessageResponse, state: RatchetState): Promise<{ text: string; state: RatchetState; failed: boolean }> => {
      try {
        const header = headerFromBase64(msg.header);
        const result = await ratchetDecrypt(state, header, msg.ciphertext);
        const text = new TextDecoder().decode(result.plaintext);
        return { text, state: result.state, failed: false };
      } catch {
        return { text: "[Decryption failed]", state, failed: true };
      }
    },
    [],
  );

  // Initialize ratchet as responder when receiving a first message with X3DH header
  const initAsResponder = useCallback(
    (x3dhHeaderB64: string, spkIndex: number): RatchetState | null => {
      if (!privateKey || !publicKey) return null;
      try {
        const x3dhHeader = x3dhHeaderFromBase64(x3dhHeaderB64);
        const sharedSecret = respondX3DH(privateKey, publicKey, spkIndex, x3dhHeader);
        const spk = deriveSignedPrekey(privateKey, spkIndex);
        return initReceiver(sharedSecret, spk);
      } catch (e) {
        console.error("X3DH respond failed:", e);
        return null;
      }
    },
    [privateKey, publicKey],
  );

  // Load and decrypt message history
  useEffect(() => {
    if (!publicKeyHex || !privateKey || !publicKey) return;

    setLoading(true);

    // Resolve peer pubkey from conversation metadata
    listConversations()
      .then((convs) => {
        const conv = convs.find((c) => c.id === conversationId);
        if (conv) {
          peerPubkeyRef.current =
            conv.participant_a === publicKeyHex ? conv.participant_b : conv.participant_a;
        }
      })
      .catch(() => {}); // non-fatal

    getMessages(conversationId)
      .then(async (msgs) => {
        if (msgs.length === 0) {
          setMessages([]);
          setLoading(false);
          return;
        }

        // Also try to determine peer from messages
        const peer = msgs.find((m) => m.sender_pubkey !== publicKeyHex);
        if (peer) peerPubkeyRef.current = peer.sender_pubkey;

        let state = ratchetRef.current;
        const decrypted: DecryptedMessage[] = [];

        for (const msg of msgs) {
          const isMine = msg.sender_pubkey === publicKeyHex;

          if (!state && !isMine && msg.x3dh_header) {
            // First message from peer with X3DH header — initialize as responder
            state = initAsResponder(msg.x3dh_header, peerSpkIndexRef.current);
          }

          if (state && !isMine) {
            const result = await decryptMessage(msg, state);
            state = result.state;
            decrypted.push({
              id: msg.id,
              text: result.text,
              senderPubkey: msg.sender_pubkey,
              isMine: false,
              timestamp: msg.created_at,
              decryptionFailed: result.failed,
            });
          } else if (isMine) {
            // Our own messages — we can't decrypt them (ratchet is one-way)
            // Show a placeholder; in production you'd store plaintext locally
            decrypted.push({
              id: msg.id,
              text: "[Your message]",
              senderPubkey: msg.sender_pubkey,
              isMine: true,
              timestamp: msg.created_at,
            });
          } else {
            decrypted.push({
              id: msg.id,
              text: "[Session not established — re-login to decrypt]",
              senderPubkey: msg.sender_pubkey,
              isMine: false,
              timestamp: msg.created_at,
              decryptionFailed: true,
            });
          }
        }

        if (state) {
          ratchetRef.current = state;
          saveSession(conversationId, state);
          setCryptoReady(true);
        }

        setMessages(decrypted);
      })
      .catch((e) => setError(e.detail || "Failed to load messages"))
      .finally(() => setLoading(false));
  }, [conversationId, publicKeyHex, privateKey, publicKey, initAsResponder, decryptMessage]);

  // Auto-scroll on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // SSE: connect and handle incoming messages
  const { lastMessage: incomingMsg, connect: connectSSE } = useMessagingStream();

  useEffect(() => {
    connectSSE();
  }, [connectSSE]);

  useEffect(() => {
    if (!incomingMsg || incomingMsg.conversation_id !== conversationId) return;
    if (incomingMsg.sender_pubkey === publicKeyHex) return; // our own echo

    (async () => {
      let state = ratchetRef.current;

      // If no session and this is the first message with X3DH header, init as responder
      if (!state && incomingMsg.x3dh_header) {
        state = initAsResponder(incomingMsg.x3dh_header, peerSpkIndexRef.current);
      }

      if (!state) {
        setMessages((prev) => [
          ...prev,
          {
            id: incomingMsg.message_id,
            text: "[Session not established — cannot decrypt]",
            senderPubkey: incomingMsg.sender_pubkey,
            isMine: false,
            timestamp: incomingMsg.created_at,
            decryptionFailed: true,
          },
        ]);
        return;
      }

      try {
        const header = headerFromBase64(incomingMsg.header);
        const result = await ratchetDecrypt(state, header, incomingMsg.ciphertext);
        ratchetRef.current = result.state;
        saveSession(conversationId, result.state);
        const text = new TextDecoder().decode(result.plaintext);

        setMessages((prev) => [
          ...prev,
          {
            id: incomingMsg.message_id,
            text,
            senderPubkey: incomingMsg.sender_pubkey,
            isMine: false,
            timestamp: incomingMsg.created_at,
          },
        ]);
      } catch {
        setMessages((prev) => [
          ...prev,
          {
            id: incomingMsg.message_id,
            text: "[Decryption failed]",
            senderPubkey: incomingMsg.sender_pubkey,
            isMine: false,
            timestamp: incomingMsg.created_at,
            decryptionFailed: true,
          },
        ]);
      }
    })();
  }, [incomingMsg, conversationId, publicKeyHex, initAsResponder]);

  const handleSend = useCallback(
    async (text: string) => {
      if (!privateKey || !publicKey || !publicKeyHex) {
        setError("Private key not available — re-login with passphrase");
        return;
      }

      const plaintext = new TextEncoder().encode(text);
      let state = ratchetRef.current;
      let x3dhHeaderB64: string | undefined;

      // If no ratchet session, initiate X3DH
      if (!state) {
        if (!peerPubkeyRef.current) {
          setError("Cannot determine peer — send a message from a conversation with a known peer");
          return;
        }

        try {
          const peerBundle = await fetchPeerPrekeys(peerPubkeyRef.current);
          const x3dhResult = await initiateX3DH(privateKey, publicKey, toPeerBundle(peerBundle));
          state = initSender(x3dhResult.sharedSecret, x3dhResult.peerDHPub);
          x3dhHeaderB64 = x3dhHeaderToBase64(x3dhResult.x3dhHeader);
          peerSpkIndexRef.current = peerBundle.signed_prekey_id;
        } catch (e: any) {
          setError(e.message || "Failed to establish encrypted session");
          return;
        }
      }

      // Encrypt with Double Ratchet
      try {
        const encrypted = await ratchetEncrypt(state, plaintext);
        state = encrypted.state;
        ratchetRef.current = state;
        saveSession(conversationId, state);
        setCryptoReady(true);

        // Send to server
        const msg = await apiSendMessage(conversationId, {
          ciphertext: encrypted.ciphertext,
          header: headerToBase64(encrypted.header),
          x3dh_header: x3dhHeaderB64 || null,
        });

        setMessages((prev) => [
          ...prev,
          {
            id: msg.id,
            text,
            senderPubkey: msg.sender_pubkey,
            isMine: true,
            timestamp: msg.created_at,
          },
        ]);
      } catch (e: any) {
        setError(e.message || "Failed to send encrypted message");
      }
    },
    [conversationId, privateKey, publicKey, publicKeyHex],
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-5 h-5 border-2 border-accent-400/30 border-t-accent-400 rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-void-700/50">
        <div className="flex items-center gap-3">
          <a href="#/messages" className="text-gray-500 hover:text-gray-300 transition-colors">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
          </a>
          <div>
            <p className="text-sm font-medium text-white">Conversation</p>
            <p className="text-[10px] font-mono text-gray-500">{conversationId.slice(0, 16)}...</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 text-[10px] text-accent-400">
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
          </svg>
          {cryptoReady ? "Signal Protocol" : "Establishing session..."}
        </div>
      </div>

      {error && (
        <div className="mx-4 mt-2 p-2 bg-red-500/10 border border-red-500/30 text-red-400 text-xs rounded">
          {error}
          <button onClick={() => setError("")} className="ml-2 text-red-500 hover:text-red-300">&times;</button>
        </div>
      )}

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4">
        {messages.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500 text-sm">No messages yet</p>
            <p className="text-gray-600 text-xs mt-1">
              Your first message will establish an encrypted session via X3DH
            </p>
          </div>
        ) : (
          messages.map((msg) => (
            <ChatBubble
              key={msg.id}
              text={msg.text}
              timestamp={msg.timestamp}
              isMine={msg.isMine}
              senderPubkey={msg.senderPubkey}
            />
          ))
        )}
      </div>

      {/* Input */}
      <ChatInput
        onSend={handleSend}
        disabled={!privateKey}
      />
    </div>
  );
}
