from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTextEdit,
    QDialog,
)
from .editar_nota_dialog import EditarNotaDialog
from PyQt5.QtCore import Qt
import os
import xml.etree.ElementTree as ET
import sqlite3
import openpyxl


class TabsNotasFiscais(QWidget):
    def __init__(self):
        super().__init__()
        self.arquivos = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Filtros
        filtro_layout = QHBoxLayout()
        self.input_cnpj = QLineEdit()
        self.input_cnpj.setPlaceholderText("Buscar por CNPJ")
        self.input_mes = QLineEdit()
        self.input_mes.setPlaceholderText("Buscar por Mês (YYYY-MM)")
        self.input_emitente = QLineEdit()
        self.input_emitente.setPlaceholderText("Buscar por Emitente")
        self.botao_buscar = QPushButton("Buscar")
        self.botao_buscar.clicked.connect(self.buscar_notas)
        filtro_layout.addWidget(self.input_cnpj)
        filtro_layout.addWidget(self.input_mes)
        filtro_layout.addWidget(self.input_emitente)
        filtro_layout.addWidget(self.botao_buscar)
        layout.addLayout(filtro_layout)

        # Botões principais
        self.botao_carregar = QPushButton("Carregar NFes (XML)")
        self.botao_carregar.clicked.connect(self.carregar_arquivos)
        self.botao_processar = QPushButton("Processar e Salvar NFes")
        self.botao_processar.clicked.connect(self.processar_xmls)
        self.botao_exportar = QPushButton("Exportar para Excel")
        self.botao_exportar.clicked.connect(self.exportar_para_excel)

        layout.addWidget(self.botao_carregar)
        layout.addWidget(self.botao_processar)
        layout.addWidget(self.botao_exportar)

        # Tabela
        self.tabela_resultado = QTableWidget()
        self.tabela_resultado.setColumnCount(7)
        self.tabela_resultado.setHorizontalHeaderLabels(
            [
                "Arquivo",
                "Emitente",
                "CNPJ",
                "Número",
                "Data de Emissão",
                "Valor Total",
                "Ações",
            ]
        )
        self.tabela_resultado.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.tabela_resultado.cellDoubleClicked.connect(self.mostrar_detalhes)
        layout.addWidget(self.tabela_resultado)

        self.setLayout(layout)

    def carregar_arquivos(self):
        arquivos, _ = QFileDialog.getOpenFileNames(
            self, "Selecionar NFes", "", "Arquivos XML (*.xml)"
        )
        if arquivos:
            self.arquivos = arquivos
            QMessageBox.information(
                self, "Arquivos Selecionados", f"{len(arquivos)} arquivos selecionados."
            )

    def processar_xmls(self):
        if not self.arquivos:
            QMessageBox.warning(self, "Aviso", "Nenhum arquivo carregado.")
            return

        conn = sqlite3.connect("app/database.db")
        cursor = conn.cursor()

        duplicadas = []
        inseridas = 0

        for caminho in self.arquivos:
            if caminho.lower().endswith(".xml"):
                try:
                    tree = ET.parse(caminho)
                    root = tree.getroot()
                    ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

                    emit = root.find(".//nfe:emit", ns)
                    nome_emitente = emit.find("nfe:xNome", ns).text
                    cnpj_emitente = emit.find("nfe:CNPJ", ns).text

                    ide = root.find(".//nfe:ide", ns)
                    numero_nota = ide.find("nfe:nNF", ns).text
                    data_emissao = ide.find("nfe:dhEmi", ns).text

                    total = root.find(".//nfe:ICMSTot", ns)
                    valor_total = float(total.find("nfe:vNF", ns).text)

                    # Verificação de duplicidade
                    cursor.execute(
                        """
                        SELECT COUNT(*) FROM notas_fiscais
                        WHERE cnpj = ? AND numero = ? AND data_emissao = ?
                    """,
                        (cnpj_emitente, numero_nota, data_emissao),
                    )
                    existe = cursor.fetchone()[0]

                    if existe:
                        duplicadas.append(os.path.basename(caminho))
                        continue

                    # Inserção
                    cursor.execute(
                        """
                        INSERT INTO notas_fiscais (arquivo, emitente, cnpj, numero, data_emissao, valor_total)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        (
                            os.path.basename(caminho),
                            nome_emitente,
                            cnpj_emitente,
                            numero_nota,
                            data_emissao,
                            valor_total,
                        ),
                    )
                    inseridas += 1

                except Exception as e:
                    QMessageBox.warning(
                        self,
                        "Erro",
                        f"Erro ao processar {os.path.basename(caminho)}: {e}",
                    )

        conn.commit()
        conn.close()

        msg = f"{inseridas} nota(s) inserida(s) com sucesso!"
        if duplicadas:
            msg += f"\nNotas ignoradas por já existirem:\n" + "\n".join(duplicadas)
        QMessageBox.information(self, "Resultado", msg)

        self.buscar_notas()

    def exportar_para_excel(self):
        try:
            conn = sqlite3.connect("app/database.db")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT arquivo, emitente, cnpj, numero, data_emissao, valor_total FROM notas_fiscais"
            )
            dados = cursor.fetchall()
            conn.close()

            if not dados:
                QMessageBox.information(
                    self, "Aviso", "Nenhuma nota fiscal encontrada para exportar."
                )
                return

            caminho_excel, _ = QFileDialog.getSaveFileName(
                self, "Salvar como", "notas_fiscais.xlsx", "Arquivos Excel (*.xlsx)"
            )
            if not caminho_excel:
                return

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Notas Fiscais"

            colunas = [
                "Arquivo",
                "Emitente",
                "CNPJ",
                "Número",
                "Data de Emissão",
                "Valor Total",
            ]
            ws.append(colunas)

            for linha in dados:
                ws.append(linha)

            wb.save(caminho_excel)
            QMessageBox.information(self, "Sucesso", f"Exportado para {caminho_excel}")

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao exportar: {e}")

    def buscar_notas(self):
        cnpj = self.input_cnpj.text().strip()
        mes = self.input_mes.text().strip()
        emitente = self.input_emitente.text().strip()

        query = "SELECT arquivo, emitente, cnpj, numero, data_emissao, valor_total FROM notas_fiscais WHERE 1=1"
        params = []

        if cnpj:
            query += " AND cnpj LIKE ?"
            params.append(f"%{cnpj}%")
        if mes:
            query += " AND substr(data_emissao, 1, 7) = ?"
            params.append(mes)
        if emitente:
            query += " AND emitente LIKE ?"
            params.append(f"%{emitente}%")

        conn = sqlite3.connect("app/database.db")
        cursor = conn.cursor()
        cursor.execute(query, params)
        resultados = cursor.fetchall()
        conn.close()

        self.tabela_resultado.setRowCount(0)
        self.tabela_resultado.setRowCount(len(resultados))

        for row_idx, row_data in enumerate(resultados):
            for col_idx, valor in enumerate(row_data):
                item = QTableWidgetItem(str(valor))
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                self.tabela_resultado.setItem(row_idx, col_idx, item)

            # Botões de ação
            btn_layout = QHBoxLayout()
            btn_editar = QPushButton("Editar")
            btn_editar.clicked.connect(lambda _, r=row_idx: self.editar_nota(r))
            btn_excluir = QPushButton("Excluir")
            btn_excluir.clicked.connect(lambda _, r=row_idx: self.excluir_nota(r))

            widget = QWidget()
            btn_layout.addWidget(btn_editar)
            btn_layout.addWidget(btn_excluir)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            widget.setLayout(btn_layout)
            self.tabela_resultado.setCellWidget(row_idx, 6, widget)

    def mostrar_detalhes(self, row, column):
        nota = {
            "arquivo": self.tabela_resultado.item(row, 0).text(),
            "emitente": self.tabela_resultado.item(row, 1).text(),
            "cnpj": self.tabela_resultado.item(row, 2).text(),
            "numero": self.tabela_resultado.item(row, 3).text(),
            "data_emissao": self.tabela_resultado.item(row, 4).text(),
            "valor_total": self.tabela_resultado.item(row, 5).text(),
        }
        dialog = DetalhesNotaDialog(nota)
        dialog.exec_()

    def editar_nota(self, row):
        cnpj = self.tabela_resultado.item(row, 2).text()
        numero = self.tabela_resultado.item(row, 3).text()
        data_emissao = self.tabela_resultado.item(row, 4).text()

        conn = sqlite3.connect("app/database.db")
        cursor = conn.cursor()
        cursor.execute(
            """
                SELECT id, emitente, cnpj, numero, data_emissao, valor_total
                FROM notas_fiscais
                WHERE cnpj = ? AND numero = ? AND data_emissao = ?
            """,
            (cnpj, numero, data_emissao),
        )
        resultado = cursor.fetchone()
        conn.close()

        if resultado:
            nota_id, emitente, cnpj, numero, data_emissao, valor_total = resultado
            dados = {
                "emitente": emitente,
                "cnpj": cnpj,
                "numero": numero,
                "data_emissao": data_emissao,
                "valor_total": valor_total,
            }

            dialog = EditarNotaDialog(nota_id, dados, self)
            if dialog.exec_() == QDialog.Accepted:
                self.buscar_notas()

    def excluir_nota(self, row):
        resposta = QMessageBox.question(
            self,
            "Excluir Nota",
            "Tem certeza que deseja excluir esta nota?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if resposta != QMessageBox.Yes:
            return

        cnpj = self.tabela_resultado.item(row, 2).text()
        numero = self.tabela_resultado.item(row, 3).text()
        data_emissao = self.tabela_resultado.item(row, 4).text()

        conn = sqlite3.connect("app/database.db")
        cursor = conn.cursor()
        cursor.execute(
            """
                DELETE FROM notas_fiscais
                WHERE cnpj = ? AND numero = ? AND data_emissao = ?
            """,
            (cnpj, numero, data_emissao),
        )

        conn.commit()
        conn.close()

        QMessageBox.information(self, "Removida", "Nota fiscal excluída com sucesso.")
        self.buscar_notas()


class DetalhesNotaDialog(QDialog):
    def __init__(self, nota):
        super().__init__()
        self.setWindowTitle(f"Detalhes da Nota: {nota['arquivo']}")
        self.setGeometry(300, 200, 600, 400)

        layout = QVBoxLayout()
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)

        detalhes = (
            f"Emitente: {nota['emitente']}\n"
            f"CNPJ: {nota['cnpj']}\n"
            f"Número: {nota['numero']}\n"
            f"Data de Emissão: {nota['data_emissao']}\n"
            f"Valor Total: {nota['valor_total']}\n"
        )
        self.text_edit.setText(detalhes)
        layout.addWidget(self.text_edit)
        self.setLayout(layout)
