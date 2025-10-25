#  Copyright (c) 2016 Phil Birkelbach
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307,
#  USA.import plugin

from functools import partial

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QPushButton, QTableWidget, QHeaderView, QTableWidgetItem

from . import connection
from . import dbItemDialog
from . import common


class CheckButton(QPushButton):
    def setChecked(self, value):
        super(CheckButton, self).setChecked(value)
        if value:
            self.setText("I")
        else:
            self.setText("0")


class DataTable(QTableWidget):
    def __init__(self, parent=None):
        super(DataTable, self).__init__(parent)
        cols = [
            "Value",
            "Annun",
            "Old",
            "Bad",
            "Fail",
            "SFail",
            "Writer",
            "Rate Avg",
            "Rate Min",
            "Rate Max",
            "Rate Std",
            "Samples",
            "Description",
        ]
        self.setColumnCount(len(cols))
        self.setHorizontalHeaderLabels(cols)
        self.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        # self.horizontalHeader().setMaximumSectionSize(int(self.width() * 20/100))

        self._col_writer = cols.index("Writer")
        self._col_rate_avg = cols.index("Rate Avg")
        self._col_rate_min = cols.index("Rate Min")
        self._col_rate_max = cols.index("Rate Max")
        self._col_rate_std = cols.index("Rate Std")
        self._col_rate_samples = cols.index("Samples")
        self._col_description = cols.index("Description")
        self._align_right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

        self.dblist = connection.db.get_item_list()
        self.dblist.sort()
        self.setRowCount(len(self.dblist))
        self.setVerticalHeaderLabels(self.dblist)
        for i, key in enumerate(self.dblist):
            item = connection.db.get_item(key)

            self._update_cell(
                i,
                self._col_description,
                item.description,
            )

            cell = common.getValueControl(item, self)
            self.setCellWidget(i, 0, cell)

            cb = CheckButton(self)
            cb.setCheckable(True)
            cb.setChecked(item.annunciate)
            cb.clicked.connect(item.setAnnunciate)
            item.annunciateChanged.connect(cb.setChecked)
            self.setCellWidget(i, 1, cb)

            cb = CheckButton(self)
            cb.setCheckable(True)
            cb.setChecked(item.old)
            cb.clicked.connect(item.setOld)
            item.oldChanged.connect(cb.setChecked)
            self.setCellWidget(i, 2, cb)

            cb = CheckButton(self)
            cb.setCheckable(True)
            cb.setChecked(item.bad)
            cb.clicked.connect(item.setBad)
            item.badChanged.connect(cb.setChecked)
            self.setCellWidget(i, 3, cb)

            cb = CheckButton(self)
            cb.setCheckable(True)
            cb.setChecked(item.fail)
            cb.clicked.connect(item.setFail)
            item.failChanged.connect(cb.setChecked)
            self.setCellWidget(i, 4, cb)

            cb = CheckButton(self)
            cb.setCheckable(True)
            cb.setChecked(item.secFail)
            cb.clicked.connect(item.setSecFail)
            item.secFailChanged.connect(cb.setChecked)
            self.setCellWidget(i, 5, cb)

            item.statsChanged.connect(partial(self._handle_stats_changed, i))
            self._handle_stats_changed(
                i,
                {
                    "last_writer": item.last_writer,
                    "avg": item.rate_avg,
                    "min": item.rate_min,
                    "max": item.rate_max,
                    "stdev": item.rate_stdev,
                    "samples": item.rate_samples,
                },
            )

        self.resizeColumnsToContents()
        self.verticalHeader().sectionDoubleClicked.connect(self.keySelected)

    def keySelected(self, x):
        key = self.verticalHeaderItem(x).text()
        d = dbItemDialog.ItemDialog(self)
        d.setKey(key)
        d.show()

    def _format_rate(self, value):
        if value is None:
            return ""
        return f"{value:.2f}"

    def _format_samples(self, value):
        if value is None:
            return ""
        return str(value)

    def _update_cell(self, row, column, value, alignment=None):
        display = "" if value is None else str(value)
        item = self.item(row, column)
        if item is None:
            item = QTableWidgetItem(display)
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            align = alignment if alignment is not None else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            item.setTextAlignment(align)
            self.setItem(row, column, item)
        else:
            item.setText(display)

    def _handle_stats_changed(self, row, stats):
        writer = stats.get("last_writer") or ""
        self._update_cell(row, self._col_writer, writer)
        self._update_cell(
            row,
            self._col_rate_avg,
            self._format_rate(stats.get("avg")),
            self._align_right,
        )
        self._update_cell(
            row,
            self._col_rate_min,
            self._format_rate(stats.get("min")),
            self._align_right,
        )
        self._update_cell(
            row,
            self._col_rate_max,
            self._format_rate(stats.get("max")),
            self._align_right,
        )
        self._update_cell(
            row,
            self._col_rate_std,
            self._format_rate(stats.get("stdev")),
            self._align_right,
        )
        self._update_cell(
            row,
            self._col_rate_samples,
            self._format_samples(stats.get("samples")),
            self._align_right,
        )
