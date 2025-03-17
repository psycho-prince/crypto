import json
import subprocess
import threading
import time
import logging
from urllib.request import Request, urlopen

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Miner:
    def __init__(self, pool, wallet, crypto, threads=1):
        self.pool = pool
        self.wallet = wallet
        self.crypto = crypto.lower()
        self.threads = threads
        self.process = None
        self.running = False
        self.api_url = "https://whattomine.com/coins.json"

    def get_profitability(self):
        """Fetch profitability data from WhatToMine."""
        ua = "Mozilla/5.0 (X11; Linux x86_64; rv:47.0) Gecko/20100101 Firefox/47.0"
        q = Request(self.api_url)
        q.add_header('User-Agent', ua)
        try:
            with urlopen(q, timeout=10) as resp:
                if resp.getcode() == 200:
                    data = json.loads(resp.read())
                    coins = data["coins"]
                    for _, coin in coins.items():
                        if coin["tag"].lower() == self.crypto:
                            logger.info(f"Profitability for {self.crypto}: {coin['profitability24']}%")
                            return float(coin["profitability24"])
                    logger.warning(f"No profitability data for {self.crypto}")
                    return 0.0
        except Exception as e:
            logger.error(f"Failed to fetch profitability: {e}")
            return 0.0

    def start_mining(self):
        """Start the mining process using xmrig (customize for other miners)."""
        self.running = True
        # Adjust command based on crypto; default to xmrig for Monero
        if self.crypto == "monero":
            cmd = f"xmrig --url {self.pool} --user {self.wallet} --coin monero -t {self.threads} --donate-level=1"
        else:
            cmd = f"xmrig --url {self.pool} --user {self.wallet} -t {self.threads} --donate-level=1"
            logger.warning(f"Using generic xmrig command for {self.crypto}; may need adjustment")
        
        logger.info(f"Starting miner: {cmd}")
        try:
            self.process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            while self.running and self.process.poll() is None:
                time.sleep(1)
            if self.running:
                self.stop_mining()
        except Exception as e:
            logger.error(f"Mining failed: {e}")
            self.running = False

    def stop_mining(self):
        """Stop the mining process cleanly."""
        if self.process and self.running:
            logger.info(f"Stopping miner for {self.crypto}")
            self.running = False
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None

    def run_in_thread(self):
        """Run mining in a background thread."""
        thread = threading.Thread(target=self.start_mining)
        thread.daemon = True
        thread.start()
        return thread
