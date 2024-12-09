import sys
import serial
import threading
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QFrame, QLineEdit, QPushButton, \
    QMessageBox, QDialog, QFileDialog, QMenuBar, QAction
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtCore import Qt, QPoint, QTimer
import json
# x, y 값을 저장할 리스트 초기화
x_history = []
y_history = []

# 시리얼 통신으로 좌표값 받기
class SerialThread(threading.Thread):
    # x, y 값을 저장할 리스트 초기화
    x_history = []
    y_history = []
    def __init__(self, port='COM3', baudrate=115200):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.x, self.y = 0, 0  # 초기 좌표
        self.running = True  # 스레드 제어
        self.open_serial()

    def open_serial(self):
        """시리얼 포트 연결"""
        try:
            self.ser = serial.Serial(self.port, baudrate=self.baudrate, timeout=1)
            print(f"시리얼 포트 {self.ser.name}에 연결됨")
        except Exception as e:
            print(f"시리얼 포트 연결 오류: {e}")
            self.ser = None

    def get_coordinates(self):
        """시리얼로부터 좌표값을 읽어옵니다."""
        if self.ser and self.ser.in_waiting > 0:
            content = self.ser.readline().decode().strip()  # 'A=<range_self>/B=<range_B>/C=<range_C>/x=<x>/y=<y>' 형식으로 받음
            print(content)  # 시리얼 데이터 확인용 출력
            try:
                # '/x=' 뒤의 값과 '/y=' 뒤의 값을 추출
                if '/x=' in content and '/y=' in content:
                    # '/x='과 '/y=' 뒤의 값을 찾아서 분리
                    parts = content.split('/x=')
                    x_part = parts[1].split('/y=')[0]
                    y_part = parts[1].split('/y=')[1]

                    # x, y 값을 float로 변환
                    new_x = float(x_part)
                    new_y = float(y_part)
                    print(f"Found position - x: {new_x} y: {new_y}")

                    # x, y 값을 각각 history에 추가하고, 5개 초과시 가장 오래된 값 제거
                    x_history.append(new_x)
                    y_history.append(new_y)

                    if len(x_history) > 5:
                        x_history.pop(0)  # 가장 오래된 x 값 제거
                    if len(y_history) > 5:
                        y_history.pop(0)  # 가장 오래된 y 값 제거

                    # x, y 값들의 평균을 계산
                    avg_x = sum(x_history) / len(x_history)
                    avg_y = sum(y_history) / len(y_history)

                    print(f"Moving average - x: {avg_x} y: {avg_y}")
                    # x, y 값을 float로 변환
                    self.x = float(avg_x)
                    self.y = float(avg_y)
                    print(f"Found position - x: {self.x} y: {self.y}")


            except ValueError:
                print("좌표값 파싱 오류")
        return self.x, self.y

    def send_position(self, position_self, position_b, position_c):
        """좌표값을 시리얼 포트를 통해 전송 (형식: anchor self:x,y;B:x,y;C:x,y)"""
        if self.ser and self.ser.is_open:
            # 전송할 데이터 포맷: anchor self:x,y;B:x,y;C:x,y
            message = f"anchor self:{position_self[0]},{position_self[1]};B:{position_b[0]},{position_b[1]};C:{position_c[0]},{position_c[1]}\n"
            self.ser.write(message.encode())  # 데이터를 바이트 형태로 인코딩하여 전송
            print(f"전송된 데이터: {message.strip()}")
        else:
            print("시리얼 포트가 열리지 않았습니다.")


# 작업장 등록, 수정 및 관련된 코드들
class InputDialog(QDialog):
    def __init__(self, data=None):
        super().__init__()
        self.data = data
        self.initUI()

    def initUI(self):
        self.setWindowTitle('작업장 설정')
        self.setGeometry(300, 300, 300, 300)
        layout = QVBoxLayout()

        # 기존 데이터 사용
        self.workspace_name_input = QLineEdit(self)
        self.workspace_width_input = QLineEdit(self)
        self.workspace_height_input = QLineEdit(self)
        self.danger_width_input = QLineEdit(self)
        self.danger_height_input = QLineEdit(self)

        # 앵커 A, B, C의 x, y 좌표 입력
        self.anchor_a_x_input = QLineEdit(self)
        self.anchor_a_y_input = QLineEdit(self)
        self.anchor_b_x_input = QLineEdit(self)
        self.anchor_b_y_input = QLineEdit(self)
        self.anchor_c_x_input = QLineEdit(self)
        self.anchor_c_y_input = QLineEdit(self)

        if self.data:
            self.workspace_name_input.setText(self.data.get("name", ""))
            self.workspace_width_input.setText(str(self.data.get("workspace_width", "")))
            self.workspace_height_input.setText(str(self.data.get("workspace_height", "")))
            self.danger_width_input.setText(str(self.data.get("danger_width", "")))
            self.danger_height_input.setText(str(self.data.get("danger_height", "")))

            # 앵커 좌표 데이터가 있을 경우 채우기
            self.anchor_a_x_input.setText(str(self.data.get("anchor_a_x", "")))
            self.anchor_a_y_input.setText(str(self.data.get("anchor_a_y", "")))
            self.anchor_b_x_input.setText(str(self.data.get("anchor_b_x", "")))
            self.anchor_b_y_input.setText(str(self.data.get("anchor_b_y", "")))
            self.anchor_c_x_input.setText(str(self.data.get("anchor_c_x", "")))
            self.anchor_c_y_input.setText(str(self.data.get("anchor_c_y", "")))

        confirm_button = QPushButton("확인", self)
        confirm_button.clicked.connect(self.accept)

        layout.addWidget(QLabel("작업장 이름:"))
        layout.addWidget(self.workspace_name_input)
        layout.addWidget(QLabel("작업 공간 가로 크기:"))
        layout.addWidget(self.workspace_width_input)
        layout.addWidget(QLabel("작업 공간 세로 크기:"))
        layout.addWidget(self.workspace_height_input)
        layout.addWidget(QLabel("위험 구역 가로 크기:"))
        layout.addWidget(self.danger_width_input)
        layout.addWidget(QLabel("위험 구역 세로 크기:"))
        layout.addWidget(self.danger_height_input)

        # 앵커 A, B, C의 좌표 입력 필드들
        layout.addWidget(QLabel("앵커 A x 좌표:"))
        layout.addWidget(self.anchor_a_x_input)
        layout.addWidget(QLabel("앵커 A y 좌표:"))
        layout.addWidget(self.anchor_a_y_input)

        layout.addWidget(QLabel("앵커 B x 좌표:"))
        layout.addWidget(self.anchor_b_x_input)
        layout.addWidget(QLabel("앵커 B y 좌표:"))
        layout.addWidget(self.anchor_b_y_input)

        layout.addWidget(QLabel("앵커 C x 좌표:"))
        layout.addWidget(self.anchor_c_x_input)
        layout.addWidget(QLabel("앵커 C y 좌표:"))
        layout.addWidget(self.anchor_c_y_input)

        layout.addWidget(confirm_button)

        self.setLayout(layout)

    def getValues(self):
        """
        사용자 입력 값을 반환합니다.
        """
        try:
            workspace_name = self.workspace_name_input.text()
            workspace_width = int(self.workspace_width_input.text())
            workspace_height = int(self.workspace_height_input.text())
            danger_width = int(self.danger_width_input.text())
            danger_height = int(self.danger_height_input.text())

            # 앵커 좌표들
            anchor_a_x = float(self.anchor_a_x_input.text())
            anchor_a_y = float(self.anchor_a_y_input.text())
            anchor_b_x = float(self.anchor_b_x_input.text())
            anchor_b_y = float(self.anchor_b_y_input.text())
            anchor_c_x = float(self.anchor_c_x_input.text())
            anchor_c_y = float(self.anchor_c_y_input.text())

            return (workspace_name, workspace_width, workspace_height,
                    danger_width, danger_height,
                    anchor_a_x, anchor_a_y,
                    anchor_b_x, anchor_b_y,
                    anchor_c_x, anchor_c_y)

        except ValueError:
            QMessageBox.warning(self, "Input Error", "모든 값을 올바르게 입력해주세요.")
            return None

# 작업장 파일 선택 및 불러오기
class UWBMonitoringSystem(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.setWindowTitle('UWB Monitoring System')
        self.setGeometry(100, 100, 600, 400)

        # QTimer 초기화
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.timerEvent)

        # 레이아웃 설정
        self.layout = QVBoxLayout()

        # 버튼 설정
        self.select_file_button = QPushButton("작업장 파일 선택", self)
        self.select_file_button.clicked.connect(self.select_file)
        self.layout.addWidget(self.select_file_button)

        # 시리얼 스레드 초기화
        self.serial_thread = None

        self.setLayout(self.layout)

    def initUI(self):
        self.setWindowTitle('UWB Monitoring System')
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # 메뉴바(MenuBar)
        menu_bar = QMenuBar(self)
        file_menu = menu_bar.addMenu("파일")
        workspace_menu = menu_bar.addMenu("작업장")

        # 파일 - 창닫기 메뉴
        close_action = QAction("창닫기", self)
        close_action.triggered.connect(self.close)
        file_menu.addAction(close_action)

        # 작업장 - 작업장 선택
        select_workspace_action = QAction("작업장 선택", self)
        select_workspace_action.triggered.connect(self.loadWorkspace)
        workspace_menu.addAction(select_workspace_action)

        # 작업장 - 작업장 정보 수정
        edit_workspace_action = QAction("작업장 정보 수정", self)
        edit_workspace_action.triggered.connect(self.editWorkspace)
        workspace_menu.addAction(edit_workspace_action)

        main_layout.setMenuBar(menu_bar)

        title = QLabel("UWB 모니터링 시스템", self)
        title.setFont(QFont("Arial", 30, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        self.load_button = QPushButton("기존 작업장 불러오기", self)
        self.load_button.clicked.connect(self.loadWorkspace)

        self.new_button = QPushButton("새 작업장 만들기", self)
        self.new_button.clicked.connect(self.createWorkspace)

        main_layout.addWidget(self.load_button)
        main_layout.addWidget(self.new_button)

    def loadWorkspace(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "작업장 불러오기", "", "JSON Files (*.json)")
        if file_name:
            try:
                with open(file_name, 'r') as file:
                    data = json.load(file)
                    self.openWorkspace(data)
                    print(f"선택된 파일: {data}")
                    #self.load_workspace_data(selected_file)

                    self.start_serial_communication()

                    # 앵커 좌표를 추출하여 시리얼로 전송
                    anchor_a = data.get('anchor_a', {})
                    anchor_b = data.get('anchor_b', {})
                    anchor_c = data.get('anchor_c', {})

                    # 앵커 좌표가 모두 존재하는 경우, 한 번에 전송
                    if 'x' in anchor_a and 'y' in anchor_a and 'x' in anchor_b and 'y' in anchor_b and 'x' in anchor_c and 'y' in anchor_c:
                        SerialThread.send_position(  # self가 SerialThread의 인스턴스인 경우
                            self.serial_thread,
                            (anchor_a['x']/100, anchor_a['y']/100),
                            (anchor_b['x']/100, anchor_b['y']/100),
                            (anchor_c['x']/100, anchor_c['y']/100)
                        )

            except Exception as e:
                QMessageBox.warning(self, "Error", f"작업장을 불러오는 중 오류가 발생했습니다: {e}")

    def createWorkspace(self):
        dialog = InputDialog()
        if dialog.exec_() == QDialog.Accepted:
            values = dialog.getValues()
            if values:
                workspace_name, workspace_width, workspace_height, danger_width, danger_height, anchor_a_x, anchor_a_y, anchor_b_x, anchor_b_y, anchor_c_x, anchor_c_y = values
                workspace_data = {
                    "name": workspace_name,
                    "workspace_width": workspace_width,
                    "workspace_height": workspace_height,
                    "danger_width": danger_width,
                    "danger_height": danger_height,
                    "anchor_a": {"x": anchor_a_x, "y": anchor_a_y},
                    "anchor_b": {"x": anchor_b_x, "y": anchor_b_y},
                    "anchor_c": {"x": anchor_c_x, "y": anchor_c_y}
                }
                self.saveWorkspace(workspace_data)
                self.openWorkspace(workspace_data)

    def saveWorkspace(self, workspace_data):
        file_name, _ = QFileDialog.getSaveFileName(self, "작업장 저장", f"{workspace_data['name']}.json", "JSON Files (*.json)")
        if file_name:
            try:
                with open(file_name, 'w') as file:
                    json.dump(workspace_data, file, indent=4)
                QMessageBox.information(self, "저장 완료", f"작업장이 {file_name}에 저장되었습니다.")
            except Exception as e:
                QMessageBox.warning(self, "Save Error", f"작업장을 저장하는 중 오류가 발생했습니다: {e}")

    def openWorkspace(self, workspace_data):
        file_name, _ = QFileDialog.getOpenFileName(self, "작업장 파일 선택", "", "JSON Files (*.json)")
        if file_name:
            self.workspace_window = WorkspaceWindow(workspace_data, workspace_file=file_name)
            self.workspace_window.show()
            self.close()
        else:
            QMessageBox.warning(self, "파일 선택 오류", "작업장 파일이 선택되지 않았습니다.")

    def editWorkspace(self):
        """
        작업장 정보를 수정하고 즉시 반영.
        """
        if hasattr(self, 'workspace_window') and self.workspace_window.workspace_data:
            current_data = self.workspace_window.workspace_data

            # 수정 다이얼로그 호출
            dialog = InputDialog(data=current_data)
            if dialog.exec_() == QDialog.Accepted:
                values = dialog.getValues()
                if values:
                    workspace_name, workspace_width, workspace_height, danger_width, danger_height = values

                    # 업데이트된 데이터
                    updated_data = {
                        "name": workspace_name,
                        "workspace_width": workspace_width,
                        "workspace_height": workspace_height,
                        "danger_width": danger_width,
                        "danger_height": danger_height
                    }

                    # 작업 공간에 반영
                    self.workspace_window.updateWorkspace(updated_data)

                    # JSON 파일 자동 갱신
                    if hasattr(self.workspace_window, 'workspace_file') and self.workspace_window.workspace_file:
                        try:
                            with open(self.workspace_window.workspace_file, 'w') as file:
                                json.dump(updated_data, file, indent=4)
                            QMessageBox.information(self, "수정 완료", "작업장이 수정되고 저장되었습니다.")
                        except Exception as e:
                            QMessageBox.warning(self, "저장 오류", f"작업장을 저장하는 중 오류가 발생했습니다: {e}")
                    else:
                        QMessageBox.warning(self, "저장 실패", "작업장 파일 정보를 찾을 수 없습니다.")
        else:
            QMessageBox.warning(self, "수정 불가", "현재 작업장이 없습니다.")

    def select_file(self):
        """작업장 파일을 선택하는 함수"""
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        file_dialog.setNameFilter("JSON Files (*.json)")

        if file_dialog.exec_():
            selected_file = file_dialog.selectedFiles()[0]
            print(f"선택된 파일: {selected_file}")
            self.load_workspace_data(selected_file)
            self.start_serial_communication() #통신 시작

    def load_workspace_data(self, file_path):
        """작업장 데이터를 파일에서 로드하는 함수"""
        try:
            with open(file_path, 'r') as file:
                data = json.load(file)
                print(f"작업장 데이터: {data}")
        except Exception as e:
            QMessageBox.warning(self, "파일 읽기 오류", f"파일을 읽는 데 오류가 발생했습니다: {e}")

    def start_serial_communication(self):
        """시리얼 통신 시작"""
        if self.serial_thread is None or not self.serial_thread.is_alive():
            self.serial_thread = SerialThread(port='COM3', baudrate=115200)
            self.serial_thread.start()
            print("시리얼 통신 시작")

        # QTimer 시작
        self.timer.start(1)  # 100ms 간격으로 timerEvent 호출

    # 위험구역 감지(1205)
    # def updateMachineStatus(self):
    #     # person이 danger zone 내에 있는지 확인
    #     person_rect = self.person.geometry()
    #     danger_rect = self.danger_zone.geometry()
    #
    #     if danger_rect.contains(person_rect.center()):
    #         self.danger_zone.setStyleSheet("background-color: #2afc69;")
    #     else:
    #         self.danger_zone.setStyleSheet("background-color: #FFD000;")

    def timerEvent(self):
            if self.serial_thread:
                # get_coordinates 호출
                x, y = self.serial_thread.get_coordinates()
                #print(f"Received coordinates: x={x}, y={y}")  # 디버깅 출력
                if hasattr(self.workspace_window, 'person') and self.workspace_window.person:
                    # 좌표를 workspace_window의 person으로 반영
                    self.workspace_window.person.move(int(x * 100), int(y * 100))  # 좌표 스케일 조정
                    self.workspace_window.updateMachineStatus() # 오류

    def closeEvent(self, event):
        """윈도우 닫을 때 시리얼 통신 종료"""
        if self.serial_thread and self.serial_thread.is_alive():
            self.serial_thread.stop()
            self.serial_thread.join()
            print("시리얼 통신 종료")
        self.timer.stop()
        event.accept()

class WorkspaceWindow(QWidget):
    def __init__(self, workspace_data, workspace_file=None):
        super().__init__()
        self.workspace_data = workspace_data
        self.workspace_file = workspace_file  # JSON 파일 경로
        self.workspace_frame = None  # 작업 공간 프레임
        self.danger_zone = None  # 위험 구역

        # 작업자 아이콘 초기화
        self.person = QLabel(self)  # QLabel 초기화
        self.person.setPixmap(QPixmap("user.png").scaled(50, 50, Qt.KeepAspectRatio))
        self.person.setFixedSize(50, 50)
        self.person.setStyleSheet("background: transparent;")
        self.person.hide()  # 초기화 상태에서는 숨김

        self.initUI()

    def initUI(self):
        """
        작업 공간 초기화. 크기 및 위험 구역 설정.
        """
        self.setWindowTitle(self.workspace_data['name'])
        layout = QVBoxLayout()
        self.setLayout(layout)

        # 작업장 이름
        title = QLabel(f"작업장: {self.workspace_data['name']}", self)
        title.setFont(QFont("Arial", 20, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 작업 공간 (회색 박스)
        self.workspace_frame = QFrame(self)
        self.updateWorkspaceFrame()
        layout.addWidget(self.workspace_frame, alignment=Qt.AlignCenter)

        # 작업자 아이콘 위치 지정 및 표시
        self.person.setParent(self.workspace_frame)  # workspace_frame 내부로 이동
        self.person.move(10, 10)  # 초기 위치 설정
        self.person.show()

        # 라벨 초기화
        self.info_label_0 = QLabel("기계 작동 여부: On", self)
        self.info_label_0.setFont(QFont("Arial", 14))
        self.info_label_0.setStyleSheet("background-color: #E0E0E0; padding: 5px; border-radius: 5px;")

        self.info_label_1 = QLabel("작업 공간 크기: -", self)
        self.info_label_1.setFont(QFont("Arial", 14))
        self.info_label_1.setStyleSheet("background-color: #E0E0E0; padding: 5px; border-radius: 5px;")

        self.info_label_2 = QLabel("UWB 센서 개수: -", self)
        self.info_label_2.setFont(QFont("Arial", 14))
        self.info_label_2.setStyleSheet("background-color: #E0E0E0; padding: 5px; border-radius: 5px;")

        self.info_label_3 = QLabel("현재 작업자 수: -", self)
        self.info_label_3.setFont(QFont("Arial", 14))
        self.info_label_3.setStyleSheet("background-color: #E0E0E0; padding: 5px; border-radius: 5px;")

        # 라벨 추가
        layout.addWidget(self.info_label_0)
        layout.addWidget(self.info_label_1)
        layout.addWidget(self.info_label_2)
        layout.addWidget(self.info_label_3)

        # 윈도우 크기 조정
        self.updateWorkspaceFrame()

    def updateWorkspace(self, updated_data):
        """
        작업 공간 정보를 업데이트하고 즉시 반영.
        """
        self.workspace_data = updated_data
        self.updateWorkspaceFrame()

        # 창 크기 업데이트
        workspace_width = self.workspace_data['workspace_width']
        workspace_height = self.workspace_data['workspace_height']
        self.setFixedSize(max(workspace_width + 200, 600), max(workspace_height + 100, 400))

        # 제목 업데이트
        self.setWindowTitle(self.workspace_data['name'])
    def updateWorkspaceFrame(self):
        """
        작업 공간 크기 및 위험 구역을 업데이트.
        """
        workspace_width = self.workspace_data['workspace_width']
        workspace_height = self.workspace_data['workspace_height']
        danger_width = self.workspace_data['danger_width']
        danger_height = self.workspace_data['danger_height']

        # 작업 공간 프레임 크기 조정
        self.workspace_frame.setFixedSize(workspace_width, workspace_height)
        self.workspace_frame.setStyleSheet("background-color: #3D3D3D;")

        # 위험 구역 업데이트
        if not self.danger_zone:
            self.danger_zone = QFrame(self.workspace_frame)
        self.danger_zone.setFixedSize(danger_width, danger_height)
        self.danger_zone.setStyleSheet("background-color: #FFD000;")
        self.danger_zone.move((workspace_width - danger_width) // 2, (workspace_height - danger_height) // 2)

        # 작업자 아이콘 위치 초기화
        if self.person:
            self.person.move(10, 10)  # 초기 위치 설정

    def updateMachineStatus(self):
        """
        기계 작동 상태 업데이트 (위험 구역 진입 여부 확인).
        """
        person_rect = self.person.geometry()
        danger_rect = self.danger_zone.geometry()

        #print(person_rect, danger_rect)

        if danger_rect is not None:
            if danger_rect.contains(person_rect.center()):
                self.danger_zone.setStyleSheet("background-color: #2afc69;")
            else:
                self.danger_zone.setStyleSheet("background-color: #FFD000;")


# PyQt5 어플리케이션 실행
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = UWBMonitoringSystem()
    window.show()

    sys.exit(app.exec_())
