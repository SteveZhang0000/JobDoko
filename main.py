import streamlit as st
import uuid
from typing import List, Dict, Optional
import os
import sys
import signal
import tempfile
import json
from pathlib import Path
import atexit
from datetime import datetime
import time
import hashlib
import secrets
from functools import wraps

# 安全配置
MAX_LOGIN_ATTEMPTS = 5
SESSION_TIMEOUT = 1800  # 30分钟无操作自动登出

# 如果是打包后的exe，重定向临时文件路径
if getattr(sys, 'frozen', False):
    tempdir = os.path.join(sys._MEIPASS, 'temp')
    os.makedirs(tempdir, exist_ok=True)
    os.environ['TEMP'] = tempdir
    os.environ['TMPDIR'] = tempdir

# 用户数据文件路径
USERS_FILE = Path("users.json")
# 任务数据文件路径
DATA_FILE = Path("task_data.json")

# 密码哈希函数
def hash_password(password: str, salt: str = None) -> tuple:
    """生成密码的PBKDF2哈希"""
    if salt is None:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return salt, key.hex()

# 用户管理类
class UserManager:
    def __init__(self):
        self.users = self._load_users()
        # 确保默认管理员存在
        if "admin" not in self.users:
            salt, hashed_pw = hash_password("admin123")
            self.users["admin"] = {
                "salt": salt,
                "hashed_password": hashed_pw,
                "role": "admin",
                "failed_attempts": 0,
                "locked": False,
                "created_at": datetime.now().isoformat()
            }
            self.save_users()
    
    def _load_users(self) -> dict:
        """从文件加载用户数据"""
        if not USERS_FILE.exists():
            # 默认管理员账户
            salt, hashed_pw = hash_password("admin123")
            return {
                "admin": {
                    "salt": salt,
                    "hashed_password": hashed_pw,
                    "role": "admin",
                    "failed_attempts": 0,
                    "locked": False
                }
            }
        
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def save_users(self):
        """保存用户数据到文件"""
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.users, f, indent=2)
    
    def add_user(self, username: str, password: str, role: str = "user") -> bool:
        """添加新用户"""
        if username in self.users:
            return False
        
        salt, hashed_pw = hash_password(password)
        self.users[username] = {
            "salt": salt,
            "hashed_password": hashed_pw,
            "role": role,
            "failed_attempts": 0,
            "locked": False
        }
        self.save_users()
        return True
    
    def verify_user(self, username: str, password: str) -> bool:
        """验证用户凭据"""
        if username not in self.users:
            return False
        
        user = self.users[username]
        
        # 检查账户是否被锁定
        if user.get("locked", False):
            return False
        
        # 验证密码
        salt = user["salt"]
        _, hashed_pw = hash_password(password, salt)
        if hashed_pw == user["hashed_password"]:
            # 重置失败计数
            user["failed_attempts"] = 0
            self.save_users()
            return True
        else:
            # 增加失败计数
            user["failed_attempts"] = user.get("failed_attempts", 0) + 1
            if user["failed_attempts"] >= MAX_LOGIN_ATTEMPTS:
                user["locked"] = True
                st.error("账户因多次失败尝试被锁定")
            self.save_users()
            return False
    
    def is_locked(self, username: str) -> bool:
        """检查账户是否被锁定"""
        return self.users.get(username, {}).get("locked", False)

# 登录装饰器
def login_required(func):
    """确保用户已登录的装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not st.session_state.get("authenticated"):
            st.warning("请先登录")
            show_login_page()
            return
        return func(*args, **kwargs)
    return wrapper

# 会话管理
def check_session_timeout():
    """检查会话是否超时"""
    if "last_activity" not in st.session_state:
        return True
    
    elapsed = time.time() - st.session_state.last_activity
    if elapsed > SESSION_TIMEOUT:
        st.session_state.authenticated = False
        st.warning("会话已超时，请重新登录")
        return True
    return False

def update_last_activity():
    """更新最后活动时间"""
    st.session_state.last_activity = time.time()

# 登录页面
def show_login_page():
    """显示登录页面"""
    st.title("任务管理系统 - 登录")
    
    user_manager = UserManager()
    
    with st.form("login_form"):
        username = st.text_input("用户名")
        password = st.text_input("密码", type="password")
        submit = st.form_submit_button("登录")
        
        if submit:
            if user_manager.is_locked(username):
                st.error("账户已被锁定，请联系管理员")
            elif user_manager.verify_user(username, password):
                st.session_state.authenticated = True
                st.session_state.username = username
                update_last_activity()
                st.success("登录成功！")
                st.rerun()
            else:
                st.error("用户名或密码错误")

# 用户管理页面
@login_required
def show_user_management():
    """显示用户管理页面"""
    st.title("用户管理")
    
    user_manager = UserManager()
    
    # 只有管理员可以管理用户
    if st.session_state.username != "admin":
        st.warning("只有管理员可以访问此页面")
        return
    
    # 添加新用户
    with st.expander("添加新用户"):
        with st.form("add_user_form"):
            new_username = st.text_input("新用户名")
            new_password = st.text_input("密码", type="password")
            new_role = st.selectbox("角色", ["admin", "user"])
            submit = st.form_submit_button("添加用户")
            
            if submit:
                if user_manager.add_user(new_username, new_password, new_role):
                    st.success(f"用户 {new_username} 添加成功")
                else:
                    st.error("用户名已存在")
    
    # 用户列表
    st.subheader("用户列表")
    for username, user_data in user_manager.users.items():
        with st.expander(f"{username} ({user_data['role']})"):
            st.write(f"状态: {'🔒 已锁定' if user_data.get('locked', False) else '✅ 活跃'}")
            st.write(f"登录失败次数: {user_data.get('failed_attempts', 0)}")
            
            if st.button(f"重置密码 {username}"):
                new_password = secrets.token_urlsafe(8)
                salt, hashed_pw = hash_password(new_password)
                user_data["salt"] = salt
                user_data["hashed_password"] = hashed_pw
                user_data["failed_attempts"] = 0
                user_data["locked"] = False
                user_manager.save_users()
                st.success(f"用户 {username} 密码已重置为: {new_password}")
            
            if user_data.get("locked", False) and st.button(f"解锁 {username}"):
                user_data["locked"] = False
                user_data["failed_attempts"] = 0
                user_manager.save_users()
                st.success(f"用户 {username} 已解锁")

# 任务节点类
class TaskNode:
    def __init__(self, name: str, description: str = "", is_completed: bool = False, 
                 parent: Optional['TaskNode'] = None, task_id: Optional[str] = None,
                 created_at: Optional[datetime] = None):
        self.task_id = task_id if task_id else str(uuid.uuid4())
        self.name = name
        self.description = description
        self._is_completed = is_completed
        self.children: List['TaskNode'] = []
        self.parent = parent
        self.is_expanded = False
        self.created_at = created_at if created_at else datetime.now()
    
    @property
    def is_completed(self) -> bool:
        if not self.children:
            return self._is_completed
        else:
            return all(child.is_completed for child in self.children)
    
    @is_completed.setter
    def is_completed(self, value: bool):
        if not self.children:
            self._is_completed = value
            if self.parent:
                self.parent.notify_child_changed()
        else:
            st.warning("非叶子节点的状态由其子节点自动决定，不能直接设置")
    
    def add_child(self, name: str, description: str = "") -> 'TaskNode':
        child = TaskNode(name, description, parent=self)
        self.children.append(child)
        self.notify_child_changed()
        return child
    
    def remove_self(self):
        if self.parent:
            self.parent.remove_child(self)
    
    def remove_child(self, child: 'TaskNode'):
        if child in self.children:
            self.children.remove(child)
            self.notify_child_changed()
    
    def notify_child_changed(self):
        if self.parent:
            self.parent.notify_child_changed()
    
    def find_task_by_id(self, task_id: str) -> Optional['TaskNode']:
        if self.task_id == task_id:
            return self
        for child in self.children:
            found = child.find_task_by_id(task_id)
            if found:
                return found
        return None
    
    def toggle_expand(self):
        self.is_expanded = not self.is_expanded
    
    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "is_completed": self._is_completed,
            "is_expanded": self.is_expanded,
            "created_at": self.created_at.isoformat(),
            "children": [child.to_dict() for child in self.children]
        }
    
    @classmethod
    def from_dict(cls, data: Dict, parent: Optional['TaskNode'] = None) -> 'TaskNode':
        task = cls(
            name=data["name"],
            description=data["description"],
            is_completed=data["is_completed"],
            parent=parent,
            task_id=data["task_id"],
            created_at=datetime.fromisoformat(data.get("created_at")))
        task.is_expanded = data.get("is_expanded", False)
        task.children = [cls.from_dict(child, task) for child in data["children"]]
        return task

    def promote(self):
        """将任务提升一级（移动到祖父节点下）"""
        if not self.parent or not self.parent.parent:
            return False
        
        grandparent = self.parent.parent
        self.parent.remove_child(self)
        grandparent.children.append(self)
        self.parent = grandparent
        grandparent.notify_child_changed()
        return True
    
    def demote(self, sibling_index: int):
        """将任务降一级（移动到指定兄弟节点下作为子节点）"""
        if not self.parent or sibling_index < 0 or sibling_index >= len(self.parent.children):
            return False
        
        target_sibling = self.parent.children[sibling_index]
        if target_sibling == self:
            return False
        
        self.parent.remove_child(self)
        target_sibling.children.append(self)
        self.parent = target_sibling
        target_sibling.notify_child_changed()
        return True

# 辅助函数
def get_all_task_options(tasks: List[TaskNode], options: Optional[List] = None, level: int = 0) -> List:
    if options is None:
        options = []
    for task in tasks:
        options.append((task.task_id, "    " * level + task.name))
        if task.is_expanded:
            get_all_task_options(task.children, options, level + 1)
    return options

def find_task_in_list(tasks: List[TaskNode], task_id: str) -> Optional[TaskNode]:
    for task in tasks:
        found = task.find_task_by_id(task_id)
        if found:
            return found
    return None

def set_task_completed(task_id: str, completed: bool):
    task = find_task_in_list(st.session_state.root_tasks, task_id)
    if task:
        task.is_completed = completed
        st.session_state.unsaved_changes = True

# 数据持久化
def get_user_data_dir() -> Path:
    """获取用户数据目录"""
    dir_path = Path("user_data")
    dir_path.mkdir(exist_ok=True)
    return dir_path

def get_user_data_file(username: str) -> Path:
    """获取对应用户的任务数据文件路径"""
    return get_user_data_dir() / f"{username}_tasks.json"

def save_tasks_to_file(username: str, tasks):
    """将任务列表保存到用户专属文件"""
    data_file = get_user_data_file(username)
    data = [task.to_dict() for task in tasks]
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_tasks_from_file(username: str):
    """从用户专属文件加载任务列表"""
    data_file = get_user_data_file(username)
    if not data_file.exists():
        return []
    
    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [TaskNode.from_dict(task_data) for task_data in data]

def save_on_exit():
    if hasattr(st.session_state, 'root_tasks'):
        save_tasks_to_file(st.session_state.username, st.session_state.root_tasks)
        print("任务数据已自动保存")

def handle_exit(signum, frame):
    save_on_exit()
    sys.exit(0)

def setup_autosave():
    def save_before_exit():
        if 'root_tasks' not in st.session_state:
            return
            
        try:
            print(f"{datetime.now().isoformat()} 尝试自动保存...")
            save_tasks_to_file(st.session_state.username, st.session_state.root_tasks)
            print("保存成功！")
        except Exception as e:
            print(f"保存失败: {e}")
    
    atexit.register(save_before_exit)

# 主应用页面
@login_required
def main_app():
    """主应用页面"""
    if check_session_timeout():
        return
    
    update_last_activity()
    
    # 添加到 main() 函数开头
    if "last_save_time" not in st.session_state:
        st.session_state.last_save_time = time.time()
    setup_autosave()


    # 初始化用户专属任务列表
    if "root_tasks" not in st.session_state:
        st.session_state.root_tasks = load_tasks_from_file(st.session_state.username)
    
    # 所有保存操作都改为使用用户名
    def save_current_tasks():
        save_tasks_to_file(st.session_state.username, st.session_state.root_tasks)
    
    # 示例：添加任务时保存
    if st.button("添加示例任务"):
        st.session_state.root_tasks.append(TaskNode(f"{st.session_state.username}的任务示例"))
        save_current_tasks()
        st.rerun()




    
    # 顶部导航栏
    st.sidebar.title("导航")
    page = st.sidebar.radio("选择页面", ["任务管理", "用户管理"])
    
    if page == "用户管理":
        show_user_management()
        return
    
    # 任务管理页面
    st.title("🌳 任务管理系统 🌳")
    st.markdown(f"当前用户: **{st.session_state.username}** | [注销](#logout)")
    
    st.markdown("""
    **使用方法**:
    - 添加多个根任务或子任务
    - 点击▶展开父任务查看子任务
    - 点击任务名称可以编辑
    - 勾选复选框标记叶子任务为完成
    - 父任务状态自动根据子任务更新
    """)
    
    # 初始化session_state
    if "root_tasks" not in st.session_state:
        st.session_state.root_tasks = load_tasks_from_file(st.session_state.username)
    
    if "editing_task_id" not in st.session_state:
        st.session_state.editing_task_id = None
    
    if "adding_task_to" not in st.session_state:
        st.session_state.adding_task_to = None
    
    # 主界面
    st.header("任务列表")

    atexit.register(save_on_exit)
    
    # 添加根任务的表单
    with st.expander("添加新根任务", expanded=False):
        with st.form("add_root_task_form"):
            new_root_name = st.text_input("根任务名称", key="new_root_name")
            new_root_desc = st.text_area("根任务描述", key="new_root_desc")
            if st.form_submit_button("添加根任务"):
                if new_root_name:
                    st.session_state.root_tasks.append(
                        TaskNode(new_root_name, new_root_desc))
                    save_tasks_to_file(st.session_state.username, st.session_state.root_tasks)
                    st.success(f"已添加根任务 '{new_root_name}'")
                    st.rerun()
                else:
                    st.warning("请输入任务名称")
    
    with st.sidebar:
        if st.button("💾 立即保存"):
            save_tasks_to_file(st.session_state.username, st.session_state.root_tasks)
            st.toast("保存成功！")
    
    st.sidebar.caption("提示：所有更改会在退出时自动保存")
    
    if "unsaved_changes" not in st.session_state:
        st.session_state.unsaved_changes = False

    if not st.session_state.root_tasks:
        st.info("暂无任务，请添加根任务")
    else:
        def render_task(task: TaskNode, level: int = 0):
            if time.time() - st.session_state.last_save_time > 30:  # 每0.5分钟保存
                save_tasks_to_file(st.session_state.username, st.session_state.root_tasks)
                st.session_state.last_save_time = time.time()
                print(f"{datetime.now().strftime('%H:%M:%S')} 自动保存成功")
            indent_space = "&nbsp;" * 16 * level
            
            with st.container():
                cols = st.columns([0.05, 0.45, 0.2, 0.05])
                
                with cols[0]:
                    if task.children:
                        if st.button("▶" if not task.is_expanded else "▼", 
                                key=f"expand_{task.task_id}"):
                            task.toggle_expand()
                            st.rerun()
                    else:
                        checked = st.checkbox(
                            "完成任务",
                            value=task.is_completed,
                            key=f"check_{task.task_id}",
                            on_change=lambda: set_task_completed(task.task_id, not task.is_completed),
                            label_visibility="hidden"
                        )

                with cols[1]:
                    if st.session_state.editing_task_id == task.task_id:
                        new_name = st.text_input("名称", value=task.name, key=f"edit_{task.task_id}")
                        new_desc = st.text_area("描述", value=task.description, key=f"desc_{task.task_id}")
                        if st.button("保存", key=f"save_{task.task_id}"):
                            task.name = new_name
                            task.description = new_desc
                            st.session_state.editing_task_id = None
                            save_tasks_to_file(st.session_state.username, st.session_state.root_tasks)
                            st.rerun()
                        if st.button("取消", key=f"cancel_{task.task_id}"):
                            st.session_state.editing_task_id = None
                            st.rerun()
                    else:
                        status = "🟢" if task.is_completed else "❗️"
                        display_name = f"{indent_space}{status} {task.name}"
                        
                        if task.description:
                            st.caption(f"{indent_space}{task.description}", unsafe_allow_html=True)
                        
                        if task.children:
                            st.markdown(f"**{display_name}**", unsafe_allow_html=True)
                        else:
                            st.markdown(display_name, unsafe_allow_html=True)
                        
                        if task.description:
                            st.caption(f"{indent_space}{task.description}", unsafe_allow_html=True)

                with cols[2]:
                    time_str = task.created_at.strftime("%m-%d %H:%M")
                    st.markdown(f"<div style='text-align: right;'>{time_str}</div>", 
                            unsafe_allow_html=True)

                with cols[3]:
                    with st.popover("⚙️", help="点击展开操作菜单"):
                        if st.button("✏️ 编辑", key=f"btn_edit_{task.task_id}"):
                            st.session_state.editing_task_id = task.task_id
                            st.rerun()
                        
                        if st.button("➕ 子任务", key=f"btn_add_{task.task_id}"):
                            st.session_state.adding_task_to = task.task_id
                            st.rerun()
                        
                        if task.parent and st.button("⬆️ 升级", key=f"btn_promote_{task.task_id}"):
                            if task.promote():
                                save_tasks_to_file(st.session_state.username, st.session_state.root_tasks)
                                st.rerun()
                        
                        if task.parent and len(task.parent.children) > 1 and st.button("⬇️ 降级", key=f"btn_demote_{task.task_id}"):
                            st.session_state.demoting_task_id = task.task_id
                            st.rerun()
                        
                        if st.button("🗑️ 删除", key=f"btn_del_{task.task_id}"):
                            if task.parent:
                                task.remove_self()
                            else:
                                st.session_state.root_tasks.remove(task)
                            save_tasks_to_file(st.session_state.username, st.session_state.root_tasks)
                            st.rerun()
            
            if st.session_state.adding_task_to == task.task_id:
                with st.form(key=f"add_child_form_{task.task_id}"):
                    new_task_name = st.text_input("子任务名称", key=f"new_child_name_{task.task_id}")
                    new_task_desc = st.text_area("子任务描述", key=f"new_child_desc_{task.task_id}")
                    cols = st.columns(2)
                    with cols[0]:
                        if st.form_submit_button("添加"):
                            if new_task_name:
                                task.add_child(new_task_name, new_task_desc)
                                task.is_expanded = True
                                st.session_state.adding_task_to = None
                                save_tasks_to_file(st.session_state.username, st.session_state.root_tasks)
                                st.rerun()
                            else:
                                st.warning("请输入任务名称")
                    with cols[1]:
                        if st.form_submit_button("取消"):
                            st.session_state.adding_task_to = None
                            st.rerun()
            
            if hasattr(st.session_state, 'demoting_task_id') and st.session_state.demoting_task_id == task.task_id:
                with st.form(key=f"demote_form_{task.task_id}"):
                    siblings = [sib for sib in task.parent.children if sib != task]
                    sibling_options = {sib.task_id: f"{sib.name} (已有{len(sib.children)}个子任务)" 
                                    for sib in siblings}
                    
                    st.write(f"将任务 '{task.name}' 降级为哪个兄弟的子任务:")
                    selected_sibling = st.radio(
                        "选择目标兄弟节点:",
                        options=list(sibling_options.keys()),
                        format_func=lambda x: sibling_options[x],
                        key=f"demote_target_{task.task_id}"
                    )
                    
                    cols = st.columns(2)
                    with cols[0]:
                        if st.form_submit_button("确认降级"):
                            target_sibling = next(sib for sib in siblings if sib.task_id == selected_sibling)
                            if task.demote(task.parent.children.index(target_sibling)):
                                save_tasks_to_file(st.session_state.username, st.session_state.root_tasks)
                                st.session_state.demoting_task_id = None
                                st.rerun()
                            else:
                                st.error("降级失败")
                    with cols[1]:
                        if st.form_submit_button("取消"):
                            st.session_state.demoting_task_id = None
                            st.rerun()
            
            if task.is_expanded and task.children:
                for child in task.children:
                    render_task(child, level + 1)
        
        for root_task in st.session_state.root_tasks:
            render_task(root_task)
    
    # 数据管理
    st.divider()
    st.header("数据管理")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.session_state.root_tasks and st.button("导出任务数据"):
            data = [task.to_dict() for task in st.session_state.root_tasks]
            st.download_button(
                label="下载JSON",
                data=json.dumps(data, ensure_ascii=False, indent=2),
                file_name="tasks.json",
                mime="application/json"
            )
    
    with col2:
        uploaded_file = st.file_uploader("导入任务数据", type=["json"])
        if uploaded_file is not None:
            try:
                data = json.load(uploaded_file)
                st.session_state.root_tasks = [TaskNode.from_dict(task_data) for task_data in data]
                save_tasks_to_file(st.session_state.username, st.session_state.root_tasks)
                st.success("任务数据导入成功！")
                st.rerun()
            except Exception as e:
                st.error(f"导入失败: {str(e)}")

# 主函数
def main():
    st.set_page_config(layout="wide")
    
    # 初始化用户管理器
    if "user_manager" not in st.session_state:
        st.session_state.user_manager = UserManager()
    
    # 检查是否已登录
    if not st.session_state.get("authenticated"):
        show_login_page()
    else:
        # 添加注销链接
        if st.sidebar.button("注销"):
            st.session_state.authenticated = False
            st.session_state.pop("username", None)
            st.rerun()
        
        main_app()

if __name__ == "__main__":
    main()
