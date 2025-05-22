import streamlit as st
import uuid
from typing import List, Dict, Optional
import os
import sys
import signal
import tempfile
import os
import json
from pathlib import Path
import atexit
from datetime import datetime
import time

# 如果是打包后的exe，重定向临时文件路径
if getattr(sys, 'frozen', False):
    tempdir = os.path.join(sys._MEIPASS, 'temp')
    os.makedirs(tempdir, exist_ok=True)
    os.environ['TEMP'] = tempdir
    os.environ['TMPDIR'] = tempdir

class TaskNode:
    def __init__(self, name: str, description: str = "", is_completed: bool = False, 
                 parent: Optional['TaskNode'] = None, task_id: Optional[str] = None):
        self.task_id = task_id if task_id else str(uuid.uuid4())
        self.name = name
        self.description = description
        self._is_completed = is_completed
        self.children: List['TaskNode'] = []
        self.parent = parent
        self.is_expanded = False
    
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
            "children": [child.to_dict() for child in self.children]
        }
    
    @classmethod
    def from_dict(cls, data: Dict, parent: Optional['TaskNode'] = None) -> 'TaskNode':
        task = cls(
            name=data["name"],
            description=data["description"],
            is_completed=data["is_completed"],
            parent=parent,
            task_id=data["task_id"]
        )
        task.is_expanded = data.get("is_expanded", False)
        task.children = [cls.from_dict(child, task) for child in data["children"]]
        return task

    def promote(self):
        """将任务提升一级（移动到祖父节点下）"""
        if not self.parent or not self.parent.parent:
            return False  # 已经是顶级或没有祖父节点，无法提升
        
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
            return False  # 不能降级到自己下面
        
        self.parent.remove_child(self)
        target_sibling.children.append(self)
        self.parent = target_sibling
        target_sibling.notify_child_changed()
        return True

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

# def set_task_completed(task_id: str, completed: bool):
#     task = find_task_in_list(st.session_state.root_tasks, task_id)
#     if task:
#         task.is_completed = completed

# 在各个修改操作中设置标记
def set_task_completed(task_id: str, completed: bool):
    task = find_task_in_list(st.session_state.root_tasks, task_id)
    if task:
        task.is_completed = completed
        st.session_state.unsaved_changes = True

# 定义数据文件路径
DATA_FILE = Path("task_data.json")

def save_tasks_to_file(tasks):
    """将任务列表保存到文件"""
    data = [task.to_dict() for task in tasks]
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_tasks_from_file():
    """从文件加载任务列表"""
    if not DATA_FILE.exists():
        return []
    
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [TaskNode.from_dict(task_data) for task_data in data]

def save_on_exit():
    if hasattr(st.session_state, 'root_tasks'):
        save_tasks_to_file(st.session_state.root_tasks)
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
            save_tasks_to_file(st.session_state.root_tasks)
            print("保存成功！")
        except Exception as e:
            print(f"保存失败: {e}")
    
    atexit.register(save_before_exit)

def main():
        # 添加到 main() 函数开头
    if "last_save_time" not in st.session_state:
        st.session_state.last_save_time = time.time()
    setup_autosave()
    st.set_page_config(layout="wide")
    st.title("🌳 你上班像玩二游 把所有红点都点完了就可以下班了 🌳")
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
        st.session_state.root_tasks = load_tasks_from_file()
    
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
                    save_tasks_to_file(st.session_state.root_tasks)
                    st.success(f"已添加根任务 '{new_root_name}'")
                    st.rerun()
                else:
                    st.warning("请输入任务名称")
    
    with st.sidebar:
        if st.button("💾 立即保存"):
            save_tasks_to_file(st.session_state.root_tasks)
            st.toast("保存成功！")
    
    st.sidebar.caption("提示：所有更改会在退出时自动保存")
    
    if "unsaved_changes" not in st.session_state:
        st.session_state.unsaved_changes = False



    if not st.session_state.root_tasks:
        st.info("暂无任务，请添加根任务")
    else:
        def render_task(task: TaskNode, level: int = 0):
            # 在 render_task 或主循环中添加
            if time.time() - st.session_state.last_save_time > 30:  # 每0.5分钟保存
                save_tasks_to_file(st.session_state.root_tasks)
                st.session_state.last_save_time = time.time()
                print(f"{datetime.now().strftime('%H:%M:%S')} 自动保存成功")
            indent_space = "&nbsp;" * 16 * level  # 统一的缩进计算
            
            with st.container():
                # 调整列宽比例，确保第一列足够宽
                cols = st.columns([0.05, 0.55, 0.05])
                
                with cols[0]:
                    # 展开/折叠按钮（仅父任务有）
                    if task.children:
                        if st.button("▶" if not task.is_expanded else "▼", 
                                key=f"expand_{task.task_id}"):
                            task.toggle_expand()
                            st.rerun()

                    # 将复选框移动到这里，与展开按钮对齐
                    else:  # 只有叶子任务有复选框
                        checked = st.checkbox(
                            "完成任务",  # 空标签
                            value=task.is_completed,
                            key=f"check_{task.task_id}",
                            on_change=lambda: set_task_completed(task.task_id, not task.is_completed),
                            label_visibility="hidden"  # 改为hidden而不是collapsed
                        )


                with cols[1]:
                    if st.session_state.editing_task_id == task.task_id:
                        # 编辑模式
                        new_name = st.text_input("名称", value=task.name, key=f"edit_{task.task_id}")
                        new_desc = st.text_area("描述", value=task.description, key=f"desc_{task.task_id}")
                        if st.button("保存", key=f"save_{task.task_id}"):
                            task.name = new_name
                            task.description = new_desc
                            st.session_state.editing_task_id = None
                            save_tasks_to_file(st.session_state.root_tasks)
                            st.rerun()
                        if st.button("取消", key=f"cancel_{task.task_id}"):
                            st.session_state.editing_task_id = None
                            st.rerun()
                    else:
                        # 显示模式
                        status = "🟢" if task.is_completed else "❗️"
                        display_name = f"{indent_space}{status} {task.name}"
                        
                        if task.children:
                            # 父任务显示
                            st.markdown(f"**{display_name}**", unsafe_allow_html=True)
                        else:
                            # 叶子任务显示（复选框已移动到前面）
                            st.markdown(display_name, unsafe_allow_html=True)
                        
                        # 描述信息（统一缩进）
                        if task.description:
                            st.caption(f"{indent_space}{task.description}", unsafe_allow_html=True)

                # 操作按钮 - 使用Popover折叠
                with cols[2]:
                    with st.popover("⚙️", help="点击展开操作菜单"):
                        # 单列排列按钮
                        if st.button("✏️ 编辑", key=f"btn_edit_{task.task_id}"):
                            st.session_state.editing_task_id = task.task_id
                            st.rerun()
                        
                        if st.button("➕ 子任务", key=f"btn_add_{task.task_id}"):
                            st.session_state.adding_task_to = task.task_id
                            st.rerun()
                        
                        if task.parent and st.button("⬆️ 升级", key=f"btn_promote_{task.task_id}"):
                            if task.promote():
                                save_tasks_to_file(st.session_state.root_tasks)
                                st.rerun()
                        
                        if task.parent and len(task.parent.children) > 1 and st.button("⬇️ 降级", key=f"btn_demote_{task.task_id}"):
                            st.session_state.demoting_task_id = task.task_id
                            st.rerun()
                        
                        if st.button("🗑️ 删除", key=f"btn_del_{task.task_id}"):
                            if task.parent:
                                task.remove_self()
                            else:
                                st.session_state.root_tasks.remove(task)
                            save_tasks_to_file(st.session_state.root_tasks)
                            st.rerun()
            
            # 添加子任务的表单（如果点击了添加子任务按钮）
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
                                save_tasks_to_file(st.session_state.root_tasks)
                                st.rerun()
                            else:
                                st.warning("请输入任务名称")
                    with cols[1]:
                        if st.form_submit_button("取消"):
                            st.session_state.adding_task_to = None
                            st.rerun()
            
            # 降级选择表单（如果点击了降级按钮）
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
                                save_tasks_to_file(st.session_state.root_tasks)
                                st.session_state.demoting_task_id = None
                                st.rerun()
                            else:
                                st.error("降级失败")
                    with cols[1]:
                        if st.form_submit_button("取消"):
                            st.session_state.demoting_task_id = None
                            st.rerun()
            
            # 渲染子任务（如果展开）
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
                save_tasks_to_file(st.session_state.root_tasks)
                st.success("任务数据导入成功！")
                st.rerun()
            except Exception as e:
                st.error(f"导入失败: {str(e)}")

if __name__ == "__main__":
    main()
