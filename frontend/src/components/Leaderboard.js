import React, { useState, useEffect } from 'react';
import axios from 'axios';

const Leaderboard = () => {
  const [leaders, setLeaders] = useState([]);

  useEffect(() => {
    const fetchLeaderboard = async () => {
      try {
        const response = await axios.get('http://localhost:5000/api/leaderboard');
        setLeaders(response.data);
      } catch (error) {
        console.error('Failed to fetch leaderboard:', error);
      }
    };
    fetchLeaderboard();
  }, []);

  return (
    <div className="mt-4">
      <h2 className="text-xl font-semibold text-center mb-2">Leaderboard</h2>
      <div className="text-sm text-gray-400">
        {leaders.length > 0 ? (
          leaders.map((leader, index) => (
            <p key={index}>{`${index + 1}. ${leader.username}: ${leader.wins} wins`}</p>
          ))
        ) : (
          <p>No leaderboard data available.</p>
        )}
      </div>
    </div>
  );
};

export default Leaderboard;
