import ctypes
import random
import threading
import time
import tkinter as tk
from tkinter import messagebox

import mouse
import pyautogui


class StableFormatTyper:
    """逐字符键盘输入，尽量保持原文的空行、前导空格/Tab和行尾空格。"""

    EMPTY_LINE_SENTINEL = "KIMI_EMPTY_LINE_GUARD_7F3A9"

    def __init__(self, root):
        self.root = root
        self.root.title("Stable Format Typer - Fixed")
        self.root.geometry("620x470")
        self.root.resizable(True, True)
        self.root.minsize(520, 410)

        self.waiting_for_click = False
        self.content = ""
        self.target_x = None
        self.target_y = None
        self.stop_event = threading.Event()

        main_frame = tk.Frame(root, padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            main_frame,
            text="🎯 Stable Auto Typer (Fixed)",
            font=("Microsoft YaHei", 14, "bold"),
            fg="#2c3e50",
        ).pack(pady=(0, 10))

        desc_frame = tk.Frame(main_frame)
        desc_frame.pack(fill=tk.X, pady=(0, 10))

        steps = [
            ("① 在下方输入需要原文输出的内容", "#3498db"),
            ("② 点击“Write”按钮", "#3498db"),
            ("③ 到目标输入位置单击鼠标左键", "#e74c3c"),
            ("④ 脚本会重新确认焦点，并逐字符恢复格式", "#27ae60"),
        ]
        for text, color in steps:
            tk.Label(
                desc_frame,
                text=text,
                font=("Microsoft YaHei", 10),
                fg=color,
            ).pack(anchor=tk.W)

        tk.Label(
            main_frame,
            text="📝 要输入的内容：",
            font=("Microsoft YaHei", 11, "bold"),
        ).pack(anchor=tk.W, pady=(10, 5))

        text_frame = tk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.scrollbar = tk.Scrollbar(text_frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_input = tk.Text(
            text_frame,
            height=11,
            width=68,
            font=("Consolas", 10),
            bg="#fafafa",
            relief=tk.SOLID,
            bd=2,
            insertbackground="#3498db",
            yscrollcommand=self.scrollbar.set,
            undo=True,
        )
        self.text_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.config(command=self.text_input.yview)

        self.status_label = tk.Label(
            main_frame,
            text="✅ 就绪：输入内容后点击 Write",
            font=("Microsoft YaHei", 10),
            fg="#27ae60",
            relief=tk.RIDGE,
            padx=10,
            pady=5,
        )
        self.status_label.pack(fill=tk.X, pady=(0, 10))

        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 5))

        self.write_button = tk.Button(
            button_frame,
            text="✍ Write（稳定模式）",
            command=self.start_positioning,
            font=("Microsoft YaHei", 11, "bold"),
            bg="#3498db",
            fg="white",
            activebackground="#2980b9",
            activeforeground="white",
            padx=20,
            pady=10,
            cursor="hand2",
            relief=tk.RAISED,
            bd=3,
        )
        self.write_button.pack(
            side=tk.LEFT, padx=(0, 15), expand=True, fill=tk.X
        )

        self.exit_button = tk.Button(
            button_frame,
            text="❌ Exit",
            command=self.exit_app,
            font=("Microsoft YaHei", 11, "bold"),
            bg="#e74c3c",
            fg="white",
            activebackground="#c0392b",
            activeforeground="white",
            padx=20,
            pady=10,
            cursor="hand2",
            relief=tk.RAISED,
            bd=3,
        )
        self.exit_button.pack(side=tk.LEFT, expand=True, fill=tk.X)

        tk.Label(
            main_frame,
            text=(
                "💡 提示：仍建议关闭目标编辑器的自动补全、自动换行和自动格式化；"
                "脚本已处理常见自动缩进，但无法绕过所有编辑器的自定义快捷键。"
            ),
            font=("Microsoft YaHei", 9),
            fg="#7f8c8d",
            wraplength=570,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(5, 0))

        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)

    # ---------- Tkinter 线程安全辅助 ----------

    def _post_to_ui(self, func):
        try:
            self.root.after(0, func)
        except tk.TclError:
            pass

    def update_status(self, message, color="#2c3e50"):
        self._post_to_ui(
            lambda: self.status_label.config(text=message, fg=color)
        )

    def set_write_button_state(self, state):
        self._post_to_ui(lambda: self.write_button.config(state=state))

    def show_info(self, title, msg):
        self._post_to_ui(lambda: messagebox.showinfo(title, msg))

    def show_error(self, title, msg):
        self._post_to_ui(lambda: messagebox.showerror(title, msg))

    # ---------- 字符发送：不使用剪贴板 ----------

    @staticmethod
    def _send_utf16_unit(unit):
        """Windows SendInput，发送一个 UTF-16 编码单元。"""
        from ctypes import wintypes

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", wintypes.ULONG_PTR),
            ]

        class INPUT(ctypes.Structure):
            _fields_ = [
                ("type", wintypes.DWORD),
                ("ki", KEYBDINPUT),
            ]

        KEYEVENTF_UNICODE = 0x0004
        KEYEVENTF_KEYUP = 0x0002
        INPUT_KEYBOARD = 1

        user32 = ctypes.windll.user32
        user32.SendInput.argtypes = [
            wintypes.UINT,
            ctypes.POINTER(INPUT),
            ctypes.c_int,
        ]
        user32.SendInput.restype = wintypes.UINT

        extra_info = wintypes.ULONG_PTR(0)
        for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
            item = INPUT()
            item.type = INPUT_KEYBOARD
            item.ki.wVk = 0
            item.ki.wScan = unit
            item.ki.dwFlags = flags
            item.ki.time = 0
            item.ki.dwExtraInfo = extra_info
            sent = user32.SendInput(
                1, ctypes.byref(item), ctypes.sizeof(INPUT)
            )
            if sent != 1:
                raise RuntimeError("SendInput 发送 Unicode 字符失败")

    def _send_unicode_char(self, char):
        """发送 Unicode 字符；非 BMP 字符按 UTF-16 代理对发送。"""
        code_point = ord(char)
        if code_point <= 0xFFFF:
            units = [code_point]
        else:
            value = code_point - 0x10000
            units = [
                0xD800 + (value >> 10),
                0xDC00 + (value & 0x3FF),
            ]

        # 代理对应按“按下高代理、按下低代理、弹起低代理、弹起高代理”发送。
        if len(units) == 2:
            from ctypes import wintypes

            class KEYBDINPUT(ctypes.Structure):
                _fields_ = [
                    ("wVk", wintypes.WORD),
                    ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("dwExtraInfo", wintypes.ULONG_PTR),
                ]

            class INPUT(ctypes.Structure):
                _fields_ = [
                    ("type", wintypes.DWORD),
                    ("ki", KEYBDINPUT),
                ]

            KEYEVENTF_UNICODE = 0x0004
            KEYEVENTF_KEYUP = 0x0002
            INPUT_KEYBOARD = 1

            user32 = ctypes.windll.user32
            user32.SendInput.argtypes = [
                wintypes.UINT,
                ctypes.POINTER(INPUT),
                ctypes.c_int,
            ]
            user32.SendInput.restype = wintypes.UINT

            extra_info = wintypes.ULONG_PTR(0)
            items = []
            for flags, unit in (
                (KEYEVENTF_UNICODE, units[0]),
                (KEYEVENTF_UNICODE, units[1]),
                (KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, units[1]),
                (KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, units[0]),
            ):
                item = INPUT()
                item.type = INPUT_KEYBOARD
                item.ki.wVk = 0
                item.ki.wScan = unit
                item.ki.dwFlags = flags
                item.ki.time = 0
                item.ki.dwExtraInfo = extra_info
                items.append(item)

            array_type = INPUT * len(items)
            sent = user32.SendInput(
                len(items),
                ctypes.byref(array_type(*items)),
                ctypes.sizeof(INPUT),
            )
            if sent != len(items):
                raise RuntimeError("SendInput 发送非 BMP 字符失败")
        else:
            self._send_utf16_unit(units[0])

    def _type_char(self, char):
        """逐字符发送；Tab 必须作为 Tab 键，而不是普通 Unicode 字符。"""
        if char == "\t":
            pyautogui.press("tab")
        elif ord(char) < 128:
            pyautogui.write(char, interval=0.0)
        else:
            self._send_unicode_char(char)

        # 随机短延时模拟键盘间隔，也降低 IDE 吞字符的概率。
        time.sleep(random.uniform(0.045, 0.085))

    def _type_text(self, text):
        for char in text:
            if self.stop_event.is_set():
                raise InterruptedError("用户停止了输入")
            self._type_char(char)

    # ---------- 行处理 ----------

    def _replace_current_line_with(self, line):
        """
        Home 按两次可兼容“智能 Home”编辑器；Shift+End 选中本行已有内容。
        随后用真实输入替换它，因此可覆盖 IDE 自动产生的缩进。
        """
        pyautogui.press("home")
        time.sleep(0.05)
        pyautogui.press("home")
        time.sleep(0.05)
        pyautogui.hotkey("shift", "end")
        time.sleep(0.08)

        prefix_length = len(line) - len(line.lstrip(" \t"))
        prefix = line[:prefix_length]
        body = line[prefix_length:]

        for char in prefix:
            if self.stop_event.is_set():
                raise InterruptedError("用户停止了输入")
            if char == "\t":
                pyautogui.press("tab")
            else:
                pyautogui.press("space")
            time.sleep(0.035)

        self._type_text(body)

    def _clear_empty_line(self):
        """
        对真正空行使用临时标记，再删除标记。这样无论 IDE 是否自动缩进，
        都不会在空行上残留不可见空格，也不会误删上一行的换行符。
        """
        self._type_text(self.EMPTY_LINE_SENTINEL)
        time.sleep(0.08)
        pyautogui.press("home")
        time.sleep(0.05)
        pyautogui.press("home")
        time.sleep(0.05)
        pyautogui.hotkey("shift", "end")
        time.sleep(0.08)
        pyautogui.press("backspace")
        time.sleep(0.08)

    # ---------- 主流程 ----------

    def mouse_listener(self):
        print("⏳ 等待鼠标左键单击目标位置...")
        self.update_status("⏳ 请在目标输入位置单击鼠标左键...", "#e67e22")

        try:
            # 等“抬起”而不是“按下”，避免用户长按鼠标时坐标尚未生效。
            mouse.wait(button="left", target_types=("up",))
            time.sleep(0.2)

            self.target_x, self.target_y = pyautogui.position()
            print(f"✅ 已定位目标：({self.target_x}, {self.target_y})")
            self.update_status(
                f"✅ 已定位 ({self.target_x}, {self.target_y})，3 秒后开始...",
                "#27ae60",
            )
            self.start_stable_typing()

        except Exception as exc:
            print(f"❌ 定位失败：{exc}")
            self.update_status("❌ 定位失败，请重试", "#e74c3c")
            self.set_write_button_state(tk.NORMAL)
            self.waiting_for_click = False

    def start_stable_typing(self):
        content = self.content
        target_x, target_y = self.target_x, self.target_y

        def execute():
            try:
                for i in range(3, 0, -1):
                    if self.stop_event.is_set():
                        return
                    self.update_status(f"⏱ {i} 秒后开始...", "#e67e22")
                    time.sleep(1)

                if self.stop_event.is_set():
                    return
                if not content:
                    self.update_status("❌ 内容为空", "#e74c3c")
                    return

                # 倒计时期间焦点可能变化，因此开始输入前重新点击原目标坐标。
                if target_x is None or target_y is None:
                    raise RuntimeError("缺少目标坐标")
                pyautogui.click(target_x, target_y)
                time.sleep(0.25)

                print("🚀 开始逐字符输入...")
                self.update_status("🚀 正在安全恢复格式...", "#3498db")

                lines = content.split("\n")
                for index, line in enumerate(lines):
                    if self.stop_event.is_set():
                        raise InterruptedError("用户停止了输入")

                    if index > 0:
                        pyautogui.press("enter")
                        # 给 IDE 自动缩进/括号展开留出时间。
                        time.sleep(0.30)

                    if line == "":
                        self._clear_empty_line()
                    else:
                        self._replace_current_line_with(line)

                    # 关闭自动补全窗口，避免下一次 Enter 误接受补全项。
                    pyautogui.press("esc")
                    time.sleep(0.08)

                print("✅ 输入完成")
                self.update_status("✅ 输入完成", "#27ae60")
                self.show_info("✅ 完成", "文本已按原格式逐字符输入。")

            except InterruptedError:
                print("⚠ 输入已被停止")
                self.update_status("⚠ 已停止", "#e67e22")
            except pyautogui.FailSafeException:
                print("⚠ PyAutoGUI 安全保护触发（鼠标移到了屏幕角）")
                self.update_status("⚠ 已因安全保护停止", "#e67e22")
                self.show_error("⚠ 已停止", "鼠标进入屏幕角落，PyAutoGUI 安全保护已触发。")
            except Exception as exc:
                error_msg = f"发生错误：\n{exc}"
                print(f"❌ {error_msg}")
                self.update_status("❌ 输入失败", "#e74c3c")
                self.show_error("❌ 错误", error_msg)
            finally:
                self.set_write_button_state(tk.NORMAL)
                self.waiting_for_click = False

        threading.Thread(target=execute, daemon=True).start()

    def start_positioning(self):
        # end-1c 只去掉 Tkinter 的隐式末尾换行，而不是随意删除用户内容。
        text = self.text_input.get("1.0", "end-1c")
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        if not text.strip():
            messagebox.showwarning("⚠ 警告", "请先输入内容！")
            return

        if not messagebox.askyesno(
            "确认开始",
            "即将开始稳定输入。\n\n"
            "建议在目标编辑器中关闭：\n"
            "• 自动补全/IntelliSense\n"
            "• 自动格式化\n"
            "• Tab 自动转换为空格（若必须保留 Tab 字符）\n\n"
            "点击“是”后，请单击目标输入位置。",
        ):
            return

        self.content = text
        self.stop_event.clear()
        self.write_button.config(state=tk.DISABLED)
        self.waiting_for_click = True
        threading.Thread(target=self.mouse_listener, daemon=True).start()

    def exit_app(self):
        self.stop_event.set()
        try:
            self.root.destroy()
        except tk.TclError:
            pass


def main():
    root = tk.Tk()
    StableFormatTyper(root)
    print("🎯 Stable Format Typer 已启动")
    root.mainloop()


if __name__ == "__main__":
    main()