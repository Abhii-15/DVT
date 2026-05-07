# BCM Testing and Analysis Tool

A Python-based system resembling CANoe for testing and analyzing Body Control Module (BCM) models.

## Features

- CANoe-like GUI with menu bar, toolbars, and status bar
- Symbol Explorer for BCM signals
- Trace Window: Real-time CAN message logging
- Graphics Window: Plot CAN bus traffic
- Write Window: Send CAN messages with cycle options
- Analysis Window: Run data analysis
- Dockable analysis, trace, write, and symbol explorer panels (like CANoe docking)
- Filtered trace window and one-click export to CSV
- Real-time plotting with pan/zoom through PyQtGraph
- Measurement control (start/stop)
- BCM Model Simulation
- CAN Bus Interface (virtual for testing)
- Automated Testing
- Message Analysis and Visualization
- DBC-based signal decode (JSON DBC) via File->Open Configuration
- Cyclic scheduling of CAN messages from write panel
- CAPL-like script panel with Python execution (Script dock)
- UDS diagnostic service panel with mocked UDS responses
- GUI layout persistence via QSettings

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Run: `python main.py` to launch the GUI

## Usage

- **Start Measurement**: Click toolbar button to begin monitoring.
- **Trace Tab**: View incoming messages.
- **Graphics Tab**: Visualize message traffic.
- **Write Tab**: Send messages to BCM.
- **Analysis Tab**: Generate summaries.
- Symbol Explorer: Browse BCM signals.
- Modify `src/bcm_model.py` for more functions.
- Use `src/test_bcm.py` for unit tests.