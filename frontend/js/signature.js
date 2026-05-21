/**
 * RSA-PSS SHA-256 signature verification using the browser's built-in
 * Web Crypto API (window.crypto.subtle) — no external library required.
 *
 * The backend signs with salt_length=32; we must match here.
 */
const SignatureVerifier = {
  _publicKey: null,

  _pemToBinary(pem) {
    const b64 = pem
      .replace(/-----BEGIN PUBLIC KEY-----/, "")
      .replace(/-----END PUBLIC KEY-----/, "")
      .replace(/\s/g, "");
    const binaryStr = atob(b64);
    const bytes = new Uint8Array(binaryStr.length);
    for (let i = 0; i < binaryStr.length; i++) bytes[i] = binaryStr.charCodeAt(i);
    return bytes.buffer;
  },

  async _importKey() {
    if (this._publicKey) return;
    const keyBuffer = this._pemToBinary(CONFIG.RSA_PUBLIC_KEY_PEM);
    this._publicKey = await window.crypto.subtle.importKey(
      "spki",
      keyBuffer,
      { name: "RSA-PSS", hash: "SHA-256" },
      false,
      ["verify"]
    );
  },

  async verify(signedDataStr, signatureBase64) {
    await this._importKey();

    // Decode base64 signature → ArrayBuffer
    const sigBinary = atob(signatureBase64);
    const sigBuffer = new Uint8Array(sigBinary.length);
    for (let i = 0; i < sigBinary.length; i++) sigBuffer[i] = sigBinary.charCodeAt(i);

    // Encode the canonical data string as UTF-8
    const dataBuffer = new TextEncoder().encode(signedDataStr);

    return window.crypto.subtle.verify(
      { name: "RSA-PSS", saltLength: 32 },   // must match backend signer.py
      this._publicKey,
      sigBuffer.buffer,
      dataBuffer
    );
  },
};
