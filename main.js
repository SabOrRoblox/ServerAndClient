const express = require('express');
const https = require('https');
const http = require('http');
const WebSocket = require('ws');
const cors = require('cors');
const crypto = require('crypto');
const fs = require('fs');

const app = express();

const USE_HTTPS = process.env.USE_HTTPS === 'true';
const SSL_KEY = process.env.SSL_KEY || '/etc/ssl/private/key.pem';
const SSL_CERT = process.env.SSL_CERT || '/etc/ssl/certs/cert.pem';

let server;
if (USE_HTTPS && fs.existsSync(SSL_KEY) && fs.existsSync(SSL_CERT)) {
  const options = {
    key: fs.readFileSync(SSL_KEY),
    cert: fs.readFileSync(SSL_CERT)
  };
  server = https.createServer(options, app);
  console.log('HTTPS mode enabled');
} else {
  server = http.createServer(app);
  console.log('HTTP mode enabled');
}

const wss = new WebSocket.Server({ server });

app.use(express.json({ limit: '1mb' }));
app.use(cors({ origin: process.env.CORS_ORIGIN || '*' }));

const log = (type, data) => {
  console.log(`[${new Date().toISOString()}] [${type}]`, JSON.stringify(data, null, 2));
};

const users = new Map();
const sessions = new Map();
const wsClients = new Map();
const usedNonces = new Set();
const usedRestNonces = new Map();

const TOKEN_EXPIRY = 3600000;
const NONCE_TTL = 300000;

const hashPassword = (password, salt = crypto.randomBytes(16)) => {
  const hash = crypto.pbkdf2Sync(password, salt, 100000, 64, 'sha512');
  return { hash: hash.toString('hex'), salt: salt.toString('hex') };
};

const verifyPassword = (password, hashHex, saltHex) => {
  const hash = crypto.pbkdf2Sync(password, Buffer.from(saltHex, 'hex'), 100000, 64, 'sha512');
  return crypto.timingSafeEqual(Buffer.from(hashHex, 'hex'), hash);
};

const generateToken = () => {
  return {
    value: crypto.randomBytes(48).toString('base64url'),
    expires: Date.now() + TOKEN_EXPIRY
  };
};

const verifyToken = (tokenValue) => {
  const session = sessions.get(tokenValue);
  if (!session) return null;
  if (Date.now() > session.expires) {
    sessions.delete(tokenValue);
    return null;
  }
  return session.username;
};

const checkRestNonce = (nonce, username) => {
  const key = `${username}:${nonce}`;
  if (usedRestNonces.has(key)) return false;
  usedRestNonces.set(key, Date.now());
  setTimeout(() => usedRestNonces.delete(key), NONCE_TTL);
  return true;
};

const verifyEd25519 = (publicKeyB64, message, signatureB64) => {
  try {
    const crypto = require('crypto');
    const pubKey = Buffer.from(publicKeyB64, 'base64');
    const sig = Buffer.from(signatureB64, 'base64');
    const verify = crypto.createVerify('sha512');
    verify.update(message);
    verify.end();
    return verify.verify({ key: pubKey, format: 'der', type: 'spki' }, sig);
  } catch {
    return false;
  }
};

app.post('/api/register', (req, res) => {
  log('REGISTER_REQUEST', { username: req.body.username });
  const { username, password, publicKey, signature } = req.body;
  
  if (!username || !password) return res.status(400).json({ error: 'Missing fields' });
  if (username.length < 3 || password.length < 4) return res.status(400).json({ error: 'Invalid' });
  if (users.has(username)) return res.status(400).json({ error: 'Exists' });
  
  if (publicKey && signature) {
    const message = `${username}:${publicKey}`;
    if (!verifyEd25519(publicKey, message, signature)) {
      log('REGISTER_FAIL', { reason: 'Invalid signature', username });
      return res.status(400).json({ error: 'Invalid signature' });
    }
  }
  
  const { hash, salt } = hashPassword(password);
  users.set(username, { 
    passwordHash: hash, 
    passwordSalt: salt, 
    publicKey: publicKey || null,
    signature: signature || null,
    createdAt: Date.now()
  });
  
  log('REGISTER_SUCCESS', { username });
  res.json({ status: 'ok' });
});

app.post('/api/login', (req, res) => {
  log('LOGIN_REQUEST', { username: req.body.username });
  const { username, password, nonce } = req.body;
  
  if (nonce && !checkRestNonce(nonce, username)) {
    return res.status(400).json({ error: 'Replay detected' });
  }
  
  const user = users.get(username);
  if (!user || !verifyPassword(password, user.passwordHash, user.passwordSalt)) {
    log('LOGIN_FAIL', { username });
    return res.status(401).json({ error: 'Invalid' });
  }
  
  const token = generateToken();
  sessions.set(token.value, { username, expires: token.expires });
  log('LOGIN_SUCCESS', { username });
  res.json({ token: token.value, username, expires: token.expires });
});

app.post('/api/key/confirm', (req, res) => {
  const { token, publicKey, signature, nonce } = req.body;
  const username = verifyToken(token);
  
  if (!username) return res.status(401).json({ error: 'Unauthorized' });
  
  if (nonce && !checkRestNonce(nonce, username)) {
    return res.status(400).json({ error: 'Replay detected' });
  }
  
  const message = `${username}:${publicKey}`;
  if (!verifyEd25519(publicKey, message, signature)) {
    log('KEY_CONFIRM_FAIL', { reason: 'Invalid signature', username });
    return res.status(400).json({ error: 'Invalid signature' });
  }
  
  const user = users.get(username);
  user.publicKey = publicKey;
  user.signature = signature;
  users.set(username, user);
  
  log('KEY_CONFIRM', { username });
  res.json({ status: 'ok' });
});

app.get('/api/user/:username', (req, res) => {
  const { token, nonce } = req.query;
  const requester = verifyToken(token);
  if (!requester) return res.status(401).json({ error: 'Unauthorized' });
  
  if (nonce && !checkRestNonce(nonce, requester)) {
    return res.status(400).json({ error: 'Replay detected' });
  }
  
  const user = users.get(req.params.username);
  if (!user) return res.status(404).json({ error: 'Not found' });
  
  res.json({ username: req.params.username, publicKey: user.publicKey });
});

app.get('/api/users', (req, res) => {
  const { token, nonce } = req.query;
  const requester = verifyToken(token);
  if (!requester) return res.status(401).json({ error: 'Unauthorized' });
  
  if (nonce && !checkRestNonce(nonce, requester)) {
    return res.status(400).json({ error: 'Replay detected' });
  }
  
  const usersList = [];
  for (const [username, user] of users) {
    if (username !== requester) {
      usersList.push({ username, hasPublicKey: !!user.publicKey });
    }
  }
  
  res.json({ users: usersList });
});

app.post('/api/logout', (req, res) => {
  const { token } = req.body;
  if (token) {
    sessions.delete(token);
    const ws = wsClients.get(token);
    if (ws) ws.close();
    wsClients.delete(token);
  }
  res.json({ status: 'ok' });
});

app.get('/api/health', (req, res) => {
  res.json({ 
    status: 'ok', 
    timestamp: Date.now(),
    users: users.size,
    sessions: sessions.size
  });
});

const checkWsNonce = (nonce, fromUser, toUser) => {
  const key = `${fromUser}:${toUser}:${nonce}`;
  if (usedNonces.has(key)) return false;
  usedNonces.add(key);
  setTimeout(() => usedNonces.delete(key), NONCE_TTL);
  return true;
};

wss.on('connection', (ws, req) => {
  let currentUser = null;
  let currentToken = null;

  ws.on('message', (data) => {
    try {
      const msg = JSON.parse(data);

      if (msg.type === 'auth') {
        const username = verifyToken(msg.token);
        if (username) {
          currentUser = username;
          currentToken = msg.token;
          wsClients.set(currentToken, ws);
          ws.send(JSON.stringify({ type: 'auth', status: 'ok' }));
          
          const online = [];
          for (const [token, client] of wsClients) {
            const session = sessions.get(token);
            if (session) online.push(session.username);
          }
          
          for (const [_, client] of wsClients) {
            client.send(JSON.stringify({ type: 'users', users: online }));
          }
          
          log('WS_AUTH', { username: currentUser, online: online.length });
        } else {
          ws.send(JSON.stringify({ type: 'auth', status: 'error' }));
        }
      }

      if (msg.type === 'message' && currentUser) {
        if (!checkWsNonce(msg.nonce, currentUser, msg.to)) {
          ws.send(JSON.stringify({ type: 'error', error: 'Replay detected' }));
          return;
        }
        
        let targetToken = null;
        for (const [token, session] of sessions) {
          if (session.username === msg.to) {
            targetToken = token;
            break;
          }
        }
        
        const targetWs = wsClients.get(targetToken);
        if (targetWs) {
          targetWs.send(JSON.stringify({
            type: 'message',
            from: currentUser,
            ciphertext: msg.ciphertext,
            nonce: msg.nonce,
            uuid: msg.uuid,
            timestamp: msg.timestamp,
            seq: msg.seq
          }));
          log('MSG_SEND', { from: currentUser, to: msg.to, uuid: msg.uuid, seq: msg.seq });
        }
      }

      if (msg.type === 'exchange_request' && currentUser) {
        let targetToken = null;
        for (const [token, session] of sessions) {
          if (session.username === msg.to) {
            targetToken = token;
            break;
          }
        }
        
        const targetWs = wsClients.get(targetToken);
        if (targetWs) {
          const user = users.get(currentUser);
          targetWs.send(JSON.stringify({
            type: 'exchange_request',
            from: currentUser,
            publicKey: user.publicKey,
            uuid: msg.uuid
          }));
          log('EXCHANGE_REQ', { from: currentUser, to: msg.to });
        }
      }

      if (msg.type === 'exchange_response' && currentUser) {
        let targetToken = null;
        for (const [token, session] of sessions) {
          if (session.username === msg.to) {
            targetToken = token;
            break;
          }
        }
        
        const targetWs = wsClients.get(targetToken);
        if (targetWs) {
          const user = users.get(currentUser);
          targetWs.send(JSON.stringify({
            type: 'exchange_response',
            from: currentUser,
            publicKey: user.publicKey,
            uuid: msg.uuid
          }));
          log('EXCHANGE_RESP', { from: currentUser, to: msg.to });
        }
      }

      if (msg.type === 'ping') {
        ws.send(JSON.stringify({ type: 'pong', timestamp: Date.now() }));
      }

    } catch (e) {
      log('WS_ERROR', { error: e.message });
    }
  });

  ws.on('close', () => {
    if (currentToken) {
      wsClients.delete(currentToken);
      const online = [];
      for (const [token, client] of wsClients) {
        const session = sessions.get(token);
        if (session) online.push(session.username);
      }
      for (const [_, client] of wsClients) {
        client.send(JSON.stringify({ type: 'users', users: online }));
      }
      log('WS_CLOSE', { user: currentUser });
    }
  });
});

setInterval(() => {
  const now = Date.now();
  let deleted = 0;
  for (const [token, session] of sessions) {
    if (now > session.expires) {
      sessions.delete(token);
      wsClients.delete(token);
      deleted++;
    }
  }
  if (deleted > 0) log('CLEANUP', { deleted });
}, 60000);

const PORT = process.env.PORT || 5000;
server.listen(PORT, '0.0.0.0', () => {
  console.log(`\n========================================`);
  console.log(`Server running on port ${PORT}`);
  console.log(`HTTPS: ${USE_HTTPS}`);
  console.log(`========================================\n`);
});
