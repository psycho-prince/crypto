import React from 'react';

const PlayerList = ({ gameData }) => {
  if (!gameData) return null;

  const players = gameData.usernames.map((name, index) => ({
    name,
    index
  }));

  const emptySlots = Array.from({ length: 8 - players.length }, (_, i) => ({
    name: 'Waiting...',
    index: players.length + i,
    empty: true
  }));

  return (
    <div className="flex flex-wrap justify-between mb-4">
      {[...players, ...emptySlots].map((player, idx) => (
        <div key={idx} className="flex items-center mb-2">
          <div className={`avatar-frame ${player.empty ? 'empty' : `player${player.index + 1}`} mr-2`}>
            {player.name[0]?.toUpperCase() || '?'}
          </div>
          <div>
            <p className={`font-semibold ${player.empty ? 'text-gray-400' : 'text-white'}`}>
              {player.name}
            </p>
            <p className="text-sm text-gray-400">Player {player.index + 1}</p>
          </div>
        </div>
      ))}
    </div>
  );
};

export default PlayerList;
