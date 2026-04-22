import matplotlib.pyplot as plt
import pandas as pd

class Analyzer:
    def __init__(self):
        self.messages = []

    def log_message(self, msg):
        self.messages.append({
            'timestamp': msg.timestamp,
            'id': msg.arbitration_id,
            'data': msg.data
        })

    def plot_traffic(self):
        if not self.messages:
            print("No messages to plot")
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
            return "No messages logged"
        df = pd.DataFrame(self.messages)
        return df.describe()