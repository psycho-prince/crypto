import React from 'react';

const Board = ({ gameData, userId, roomId, socket }) => {
  if (!gameData || gameData.status !== 'in_progress') return null;

  const handleCellClick = (row, col) => {
    if (gameData.status !== 'in_progress' || gameData.currentTurn !== userId) return;
    socket.emit('make_move', { roomId, userId, row, col });
  };

  return (
    <div className="grid grid-cols-9 gap-1 mb-4">
      {gameData.board.map((row, rowIdx) =>
        row.map((cell, colIdx) => {
          const atoms = cell % 10;
          const player = Math.floor(cell / 10);
          return (
            <div
              key={`${rowIdx}-${colIdx}`}
              className={`cell ${player > 0 ? `player${player}` : ''} ${
                gameData.currentTurn !== userId ? 'disabled' : ''
              }`}
              data-row={rowIdx}
              data-col={colIdx}
              onClick={() => handleCellClick(rowIdx, colIdx)}
            >
              {atoms > 0 ? atoms : ''}
            </div>
          );
        })
      )}
    </div>
  );
};

export default Board;
