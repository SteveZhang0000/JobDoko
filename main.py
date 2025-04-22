import streamlit as st
import uuid
from typing import List, Dict, Optional

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

def main():
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
    
    if "root_tasks" not in st.session_state:
        st.session_state.root_tasks: List[TaskNode] = []
    
    if "editing_task_id" not in st.session_state:
        st.session_state.editing_task_id = None
    
    # 侧边栏
    with st.sidebar:
        st.header("任务操作")
        
        st.subheader("添加根任务")
        new_root_name = st.text_input("根任务名称", key="new_root_name")
        new_root_desc = st.text_area("根任务描述", key="new_root_desc")
        if st.button("添加根任务"):
            if new_root_name:
                st.session_state.root_tasks.append(
                    TaskNode(new_root_name, new_root_desc)
                )
                st.success(f"已添加根任务 '{new_root_name}'")
            else:
                st.warning("请输入任务名称")
        
        st.subheader("添加子任务")
        if st.session_state.root_tasks:
            parent_task_id = st.selectbox(
                "父任务",
                options=get_all_task_options(st.session_state.root_tasks),
                format_func=lambda x: x[1],
                key="parent_task_select"
            )
            new_task_name = st.text_input("子任务名称", key="new_child_name")
            new_task_desc = st.text_area("子任务描述", key="new_child_desc")
            if st.button("添加子任务"):
                if new_task_name:
                    parent_task = find_task_in_list(st.session_state.root_tasks, parent_task_id[0])
                    if parent_task:
                        parent_task.add_child(new_task_name, new_task_desc)
                        parent_task.is_expanded = True
                        st.success(f"已添加子任务 '{new_task_name}'")
                    else:
                        st.error("找不到父任务")
                else:
                    st.warning("请输入任务名称")
        else:
            st.warning("请先添加根任务")
    
    # 主界面
    st.header("任务列表")
    
    if not st.session_state.root_tasks:
        st.info("暂无任务，请从侧边栏添加根任务")
    else:
        def render_task(task: TaskNode, level: int = 0):
            indent_space = "&nbsp;" * 4 * level  # 统一的缩进计算
            
            with st.container():
                cols = st.columns([0.05, 0.7, 0.15, 0.1])
                
                with cols[0]:
                    # 展开/折叠按钮（仅父任务有）
                    if task.children:
                        if st.button("▶" if not task.is_expanded else "▼", 
                                key=f"expand_{task.task_id}"):
                            task.toggle_expand()
                            st.experimental_rerun()
                    else:
                        st.write("", key=f"placeholder_{task.task_id}")  # 叶子任务占位保持对齐
                
                with cols[1]:
                    if st.session_state.editing_task_id == task.task_id:
                        # 编辑模式
                        new_name = st.text_input("名称", value=task.name, key=f"edit_{task.task_id}")
                        new_desc = st.text_area("描述", value=task.description, key=f"desc_{task.task_id}")
                        if st.button("保存", key=f"save_{task.task_id}"):
                            task.name = new_name
                            task.description = new_desc
                            st.session_state.editing_task_id = None
                            st.experimental_rerun()
                        if st.button("取消", key=f"cancel_{task.task_id}"):
                            st.session_state.editing_task_id = None
                            st.experimental_rerun()
                    else:
                        # 显示模式
                        status = "✓" if task.is_completed else "✗"
                        display_name = f"{indent_space}{status} {task.name}"
                        
                        if task.children:
                            # 父任务显示
                            st.markdown(f"**{display_name}**", unsafe_allow_html=True)
                        else:
                            # 叶子任务显示（使用checkbox）
                            checked = st.checkbox(
                                display_name,
                                value=task.is_completed,
                                key=f"check_{task.task_id}",
                                on_change=lambda: set_task_completed(task.task_id, not task.is_completed),
                                label_visibility="visible"
                            )
                        
                        # 描述信息（统一缩进）
                        if task.description:
                            st.caption(f"{indent_space}{task.description}", unsafe_allow_html=True)
                
                # 操作按钮列（保持对齐）
                with cols[2]:
                    if st.button("编辑", key=f"btn_edit_{task.task_id}"):
                        st.session_state.editing_task_id = task.task_id
                        st.experimental_rerun()
                
                with cols[3]:
                    if st.button("删除", key=f"btn_del_{task.task_id}"):
                        if task.parent:
                            task.remove_self()
                        else:
                            st.session_state.root_tasks.remove(task)
                        st.experimental_rerun()
            
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
                data=str(data),
                file_name="tasks.json",
                mime="application/json"
            )
    
    with col2:
        uploaded_file = st.file_uploader("导入任务数据", type=["json"])
        if uploaded_file is not None:
            try:
                import json
                data = json.load(uploaded_file)
                st.session_state.root_tasks = [TaskNode.from_dict(task_data) for task_data in data]
                st.success("任务数据导入成功！")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"导入失败: {str(e)}")



if __name__ == "__main__":
    main()