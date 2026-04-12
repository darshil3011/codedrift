// Auth utilities fixture

const SECRET = 'js-secret';

function generateToken(userId, role) {
  return `${userId}:${role}:sig`;
}

function validateToken(token) {
  const parts = token.split(':');
  if (parts.length !== 3) return null;
  const [userId, role] = parts;
  return { userId, role };
}

const isTokenRevoked = (token) => {
  return false;
};

module.exports = { generateToken, validateToken, isTokenRevoked };
