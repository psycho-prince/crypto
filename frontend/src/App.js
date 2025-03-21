import React, { useState, useEffect } from 'react';
import io from 'socket.io-client';
import axios from 'axios';
import Board from './components/Board';
import PlayerList from './components/PlayerList';
import Leaderboard from './components/Leaderboard';

const socket = io('http://localhost:5000');

function App() {
  const [userId, setUserId] = useState(new URLSearchParams(window.location.search).get('user_id') || 'test_user');
  const [username, setUsername] = useState(new URLSearchParams(window.location.search).get('username') || 'Test User');
  const [roomId, setRoomId] = useState(new URLSearchParams(window.location.search).get('room_id') || '');
  const [gameData, setGameData] = useState(null);
  const [toast, setToast] = useState('');

  useEffect(() => {
    if (window.Telegram && window.Telegram.WebApp) {
      window.Telegram.WebApp.ready();
      window.Telegram.WebApp.expand();
    }

    socket.on('game_created', ({ roomId, gameData }) => {
      setRoomId(roomId);
      setGameData(gameData);
    });

    socket.on('game_start', (data) => {
      setGameData(data);
    });

    socket.on('game_update', (data) => {
      setGameData(data);
    });

    socket.on('chain_reaction', (reactions) => {
      reactions.forEach((reaction, index) => {
        setTimeout(() => {
          const cell = document.querySelector(`.cell[data-row="${reaction.row}"][data-col="${reaction.col}"]`);
          if (cell) cell.classList.add('explode');
        }, index * 200);
      });
    });

    socket.on('player_joined', ({ username }) => {
      setToast(`${username} joined the game!`);
    });

    socket.on('join_error', ({ error }) => {
      alert(error);
    });

    socket.on('error', ({ error }) => {
      alert(error);
    });

    if (roomId) {
      socket.emit('join_game', { roomId, userId, username });
    }

    return () => {
      socket.off('game_created');
      socket.off('game_start');
      socket.off('game_update');
      socket.off('chain_reaction');
      socket.off('player_joined');
      socket.off('join_error');
      socket.off('error');
    };
  }, [roomId, userId, username]);

  const handleStartGame = () => {
    socket.emit('create_game', { userId, username });
  };

  const handleShareLink = () => {
    const gameUrl = `http://localhost:3000/?user_id=${userId}&username=${username}&room_id=${roomId}`;
    navigator.clipboard.writeText(gameUrl).then(() => {
      alert('Game link copied to clipboard!');
    }).catch(() => {
      alert('Failed to copy link. Copy manually: ' + gameUrl);
    });
  };

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(''), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  return (
    <div className="p-6 rounded-lg shadow-lg w-full max-w-md">
      <h1 className="text-3xl font-bold text-center mb-4">Chain Reaction</h1>
      <PlayerList gameData={gameData} />
      <div className="text-center mb-4 text-lg font-semibold">
        {gameData?.status === 'not_started'
          ? 'Waiting for players...'
          : gameData?.status === 'in_progress'
          ? `Game in Progress - ${gameData.currentTurn === userId ? 'Your Turn' : `${gameData.usernames[gameData.players.indexOf(gameData.currentTurn)]}'s Turn`}`
          : gameData?.status === 'finished'
          ? `Game Over! Winner: ${gameData.usernames[gameData.winner - 1]}`
          : 'Click "Start Game" to begin!'}
      </div>
      <Board gameData={gameData} userId={userId} roomId={roomId} socket={socket} />
      <div className="text-center mb-4">
        <p className="text-sm text-gray-400">User ID: {userId}</p>
        <p className="text-sm text-gray-400">Room ID: {roomId || 'Not yet created'}</p>
      </div>
      {!gameData || gameData.status === 'not_started' ? (
        <>
          <button
            onClick={handleStartGame}
            className="bg-green-500 text-white px-4 py-2 rounded w-full hover:bg-green-600 mb-2"
          >
            Start Game
          </button>
          {roomId && (
            <button
              onClick={handleShareLink}
              className="bg-blue-500 text-white px-4 py-2 rounded w-full hover:bg-blue-600"
            >
              Share Game Link
            </button>
          )}
        </>
      ) : null}
      <Leaderboard />
      {toast && <div className="toast" style={{ display: 'block' }}>{toast}</div>}
    </div>
  );
}

export default App;
