import matplotlib.pyplot as plt
import pandas as pd


class Analyzer:
    def __init__(self):
        self.messages = []

    def log_message(self, msg):
        self.messages.append({
            'timestamp': msg.timestamp,
            'id': msg.arbitration_id,
            'data': msg.data,
        })

    def dataframe(self):
        return pd.DataFrame(self.messages)

    def frame_frequency(self):
        if len(self.messages) < 2:
            return 0.0
        timestamps = [float(msg['timestamp']) for msg in self.messages if 'timestamp' in msg]
        if len(timestamps) < 2:
            return 0.0
        span = timestamps[-1] - timestamps[0]
        if span <= 0:
            return 0.0
        return max(0.0, (len(timestamps) - 1) / span)

    def bus_load_percent(self, bitrate_kbps=500, avg_bits_per_frame=128):
        if bitrate_kbps <= 0:
            return 0.0
        frames_per_sec = self.frame_frequency()
        bits_per_sec = bitrate_kbps * 1000
        load = (frames_per_sec * avg_bits_per_frame) / bits_per_sec * 100.0
        return max(0.0, min(load, 100.0))

    def plot_traffic(self):
        if not self.messages:
            print('No messages to plot')
            return

        df = pd.DataFrame(self.messages)
        plt.figure(figsize=(10, 5))
        plt.scatter(df['timestamp'], df['id'], c='blue', label='Messages')
        plt.xlabel('Time')
        plt.ylabel('CAN ID')
        plt.title('CAN Bus Traffic')
        plt.show()

    def summary(self):
        if not self.messages:
            return 'No messages logged'
        df = pd.DataFrame(self.messages)
        return df.describe()
