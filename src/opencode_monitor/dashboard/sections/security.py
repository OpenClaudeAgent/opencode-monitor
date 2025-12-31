"""
Security section - risk analysis.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QScrollArea,
)
from PyQt6.QtCore import Qt

from ..widgets import (
    MetricsRow,
    DataTable,
    SectionHeader,
    Separator,
    PageHeader,
    EmptyState,
)
from ..styles import SPACING, COL_WIDTH, UI
from .colors import get_operation_variant


class SecuritySection(QWidget):
    """Security section - risk analysis."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["lg"]
        )
        layout.setSpacing(0)

        header = PageHeader("Security", "Risk analysis of executed operations")
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, SPACING["md"], 0)
        content_layout.setSpacing(SPACING["xl"])

        # Security Metrics (5 cards with risk colors)
        self._metrics = MetricsRow()
        self._metrics.add_metric("total", "0", "Analyzed", "primary")
        self._metrics.add_metric("critical", "0", "Critical", "error")
        self._metrics.add_metric("high", "0", "High", "warning")
        self._metrics.add_metric("medium", "0", "Medium", "warning")
        self._metrics.add_metric("low", "0", "Low", "success")
        self._metrics.add_stretch()
        content_layout.addWidget(self._metrics)

        content_layout.addWidget(Separator())

        # Critical Alerts Section
        content_layout.addWidget(
            SectionHeader("Critical Alerts", "High-risk operations requiring attention")
        )

        self._critical_table = DataTable(["Type", "Details", "Risk", "Reason"])
        self._critical_table.setColumnWidth(0, COL_WIDTH["type"])  # Operation type
        self._critical_table.setColumnWidth(1, COL_WIDTH["path"])  # Details/path
        self._critical_table.setColumnWidth(2, COL_WIDTH["risk"])  # Risk level
        content_layout.addWidget(self._critical_table)

        self._critical_empty = EmptyState(
            icon="✓",
            title="No critical alerts",
            subtitle="All operations within normal risk levels",
        )
        self._critical_empty.hide()
        content_layout.addWidget(self._critical_empty)

        content_layout.addWidget(Separator())

        # Recent Commands Section
        content_layout.addWidget(
            SectionHeader("Recent Commands", "Last analyzed shell commands")
        )

        self._commands_table = DataTable(["Command", "Risk", "Score", "Reason"])
        self._commands_table.setColumnWidth(0, COL_WIDTH["path"])  # Command (long text)
        self._commands_table.setColumnWidth(1, COL_WIDTH["risk"])  # Risk level
        self._commands_table.setColumnWidth(2, COL_WIDTH["number_tiny"])  # Score
        self._commands_table.setColumnWidth(2, 80)
        content_layout.addWidget(self._commands_table)

        content_layout.addWidget(Separator())

        # File Operations Section
        content_layout.addWidget(
            SectionHeader("File Operations", "Recent file reads and writes")
        )

        self._files_table = DataTable(["Operation", "Path", "Risk", "Score"])
        self._files_table.setColumnWidth(0, COL_WIDTH["type"])  # Operation type
        self._files_table.setColumnWidth(1, COL_WIDTH["path"])  # File path
        self._files_table.setColumnWidth(2, COL_WIDTH["risk"])  # Risk level
        self._files_table.setColumnWidth(3, COL_WIDTH["number_tiny"])  # Score
        content_layout.addWidget(self._files_table)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def update_data(
        self,
        stats: dict,
        commands: list[dict],
        files: list[dict],
        critical_items: list[dict] | None = None,
    ) -> None:
        """Update security data."""
        self._metrics.update_metric("total", str(stats.get("total", 0)))
        self._metrics.update_metric("critical", str(stats.get("critical", 0)))
        self._metrics.update_metric("high", str(stats.get("high", 0)))
        self._metrics.update_metric("medium", str(stats.get("medium", 0)))
        self._metrics.update_metric("low", str(stats.get("low", 0)))

        # Critical alerts
        self._critical_table.clear_data()

        if critical_items:
            sorted_items = sorted(
                critical_items, key=lambda x: x.get("score", 0), reverse=True
            )

            if sorted_items:
                self._critical_table.show()
                self._critical_empty.hide()

                for item in sorted_items[: UI["table_row_limit"]]:
                    risk = item.get("risk", "low").lower()
                    risk_class = f"risk-{risk}"
                    details = item.get("details", "")
                    reason = item.get("reason", "")
                    item_type = item.get("type", "")
                    type_variant = get_operation_variant(item_type)

                    self._critical_table.add_row(
                        [
                            (item_type.upper(), type_variant)
                            if type_variant
                            else item_type.upper(),
                            details,
                            (risk.upper(), risk_class),
                            reason,
                        ],
                        full_values=[
                            item_type.upper(),
                            details,
                            risk.upper(),
                            reason,
                        ],
                    )
            else:
                self._critical_table.hide()
                self._critical_empty.show()
        else:
            self._critical_table.hide()
            self._critical_empty.show()

        # Commands
        self._commands_table.clear_data()
        for cmd in commands[: UI["table_row_limit"]]:
            risk = cmd.get("risk", "low").lower()
            risk_class = f"risk-{risk}"
            command = cmd.get("command", "")
            reason = cmd.get("reason", "")

            self._commands_table.add_row(
                [
                    command,
                    (risk.upper(), risk_class),
                    str(cmd.get("score", 0)),
                    reason,
                ],
                full_values=[command, risk.upper(), str(cmd.get("score", 0)), reason],
            )

        # Files
        self._files_table.clear_data()
        for f in files[: UI["table_row_limit"]]:
            risk = f.get("risk", "low").lower()
            risk_class = f"risk-{risk}"
            path = f.get("path", "")
            operation = f.get("operation", "")
            op_variant = get_operation_variant(operation)

            self._files_table.add_row(
                [
                    (operation.upper(), op_variant)
                    if op_variant
                    else operation.upper(),
                    path,
                    (risk.upper(), risk_class),
                    str(f.get("score", 0)),
                ],
                full_values=[
                    operation.upper(),
                    path,
                    risk.upper(),
                    str(f.get("score", 0)),
                ],
            )
