from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import QGraphicsEllipseItem, QGraphicsItem, QGraphicsLineItem, QGraphicsScene, QGraphicsTextItem, QGraphicsView


class ECUNodeItem(QGraphicsEllipseItem):
    def __init__(self, name, x, y, on_moved=None):
        super().__init__(-40, -20, 80, 40)
        self.name = name
        self.on_moved = on_moved
        self.setPos(x, y)
        self.setBrush(QBrush(QColor('#3a7bd5')))
        self.setPen(QPen(QColor('#6aa7ff'), 1.5))
        self.setFlags(
            QGraphicsEllipseItem.ItemIsMovable
            | QGraphicsEllipseItem.ItemIsSelectable
            | QGraphicsEllipseItem.ItemSendsGeometryChanges
        )
        self.label = QGraphicsTextItem(name, self)
        self.label.setDefaultTextColor(QColor('white'))
        self.label.setFont(QFont('Segoe UI', 9, QFont.Bold))
        self.label.setPos(-self.label.boundingRect().width() / 2, -10)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.on_moved:
            self.on_moved(self.name, value)
        return super().itemChange(change, value)

    def set_highlighted(self, highlighted):
        self.setBrush(QBrush(QColor('#f5a742' if highlighted else '#3a7bd5')))
        self.setPen(QPen(QColor('#ffd28a' if highlighted else '#6aa7ff'), 2 if highlighted else 1.5))


class CANBusGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor('#1e1e1e'))
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.nodes = {}
        self.bus_lines = []
        self._init_bus_lines()
        self.setDragMode(QGraphicsView.RubberBandDrag)

    def _init_bus_lines(self):
        self.scene.clear()
        self.nodes.clear()
        self.bus_lines.clear()
        width = 1600
        self.scene.setSceneRect(QRectF(0, 0, width, 700))
        self.scene.addLine(60, 260, width - 60, 260, QPen(QColor('#cc3333'), 3))
        self.scene.addLine(60, 360, width - 60, 360, QPen(QColor('#33aa33'), 3))
        self.scene.addText('CAN_H', QFont('Segoe UI', 10, QFont.Bold)).setPos(10, 245)
        self.scene.addText('CAN_L', QFont('Segoe UI', 10, QFont.Bold)).setPos(10, 345)

    def add_node(self, name, x=None, y=None):
        if name in self.nodes:
            return self.nodes[name]
        x = x if x is not None else 140 + len(self.nodes) * 180
        y = y if y is not None else 120
        node = ECUNodeItem(name, x, y, self._node_moved)
        self.scene.addItem(node)
        self.nodes[name] = node
        drop = self.scene.addLine(x, y + 20, x, 260, QPen(QColor('#888888'), 1, Qt.DashLine))
        self.bus_lines.append((name, drop))
        return node

    def _node_moved(self, name, pos):
        for node_name, line in self.bus_lines:
            if node_name == name:
                line.setLine(pos.x(), pos.y() + 20, pos.x(), 260)
                break

    def highlight_node(self, name):
        for node_name, node in self.nodes.items():
            node.set_highlighted(node_name == name)

    def clear_highlights(self):
        for node in self.nodes.values():
            node.set_highlighted(False)
