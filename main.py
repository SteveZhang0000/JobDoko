import streamlit as st
from streamlit.components.v1 import html
import uuid


# 辅助函数
def get_all_task_options(task, options=None, level=0):
    if options is None:
        options = []
    options.append((task.task_id, "    " * level + task.name))
    for child in task.children:
        get_all_task_options(child, options, level + 1)
    return options

def set_task_completed(task_id, completed):
    task = st.session_state.root_task.find_task_by_id(task_id)
    if task:
        task.is_completed = completed


class TaskNode:
    def __init__(self, name, description="", is_completed=False, parent=None, task_id=None):
        """
        初始化任务节点
        
        参数:
            name: 任务名称
            description: 任务描述
            is_completed: 初始完成状态
            parent: 父任务
            task_id: 任务唯一ID
        """
        self.task_id = task_id if task_id else str(uuid.uuid4())
        self.name = name
        self.description = description
        self._is_completed = is_completed
        self.children = []
        self.parent = parent
    
    @property
    def is_completed(self):
        """获取任务完成状态(自动计算)"""
        if not self.children:  # 如果是叶子节点
            return self._is_completed
        else:  # 如果是父节点，状态由子节点决定
            return all(child.is_completed for child in self.children)
    
    @is_completed.setter
    def is_completed(self, value):
        """设置任务完成状态(仅对叶子节点有效)"""
        if not self.children:  # 只有叶子节点可以直接设置状态
            self._is_completed = value
            # 状态改变后需要通知父节点更新
            if self.parent:
                self.parent.notify_child_changed()
        else:
            st.warning("非叶子节点的状态由其子节点自动决定，不能直接设置")
    
    def add_child(self, name, description=""):
        """添加子任务"""
        child = TaskNode(name, description, parent=self)
        self.children.append(child)
        self.notify_child_changed()
        return child
    
    def remove_child(self, child):
        """移除子任务"""
        if child in self.children:
            self.children.remove(child)
            self.notify_child_changed()
    
    def notify_child_changed(self):
        """子节点变化时通知父节点更新状态"""
        if self.parent:
            self.parent.notify_child_changed()
    
    def find_task_by_id(self, task_id):
        """根据ID查找任务"""
        if self.task_id == task_id:
            return self
        for child in self.children:
            found = child.find_task_by_id(task_id)
            if found:
                return found
        return None
    
    def to_dict(self):
        """将任务转换为字典(用于序列化)"""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "is_completed": self._is_completed,
            "children": [child.to_dict() for child in self.children]
        }
    
    @classmethod
    def from_dict(cls, data, parent=None):
        """从字典创建任务(用于反序列化)"""
        task = cls(
            name=data["name"],
            description=data["description"],
            is_completed=data["is_completed"],
            parent=parent,
            task_id=data["task_id"]
        )
        task.children = [cls.from_dict(child, task) for child in data["children"]]
        return task
    
    def __repr__(self):
        status = "✓" if self.is_completed else "✗"
        return f"{status} {self.name} ({len(self.children)}子任务)"

# Streamlit应用
def main():
    st.title("🌳 树形任务管理系统")
    st.markdown("""
    **使用方法**:
    - 添加根任务或子任务
    - 点击任务名称可以编辑
    - 勾选复选框标记叶子任务为完成
    - 父任务状态自动根据子任务更新
    """)
    
    # 初始化会话状态
    if "root_task" not in st.session_state:
        st.session_state.root_task = TaskNode("我的项目")
    
    if "editing_task_id" not in st.session_state:
        st.session_state.editing_task_id = None
    
    # 侧边栏 - 添加任务
    with st.sidebar:
        st.header("添加任务")
        parent_task_id = st.selectbox(
            "父任务",
            options=get_all_task_options(st.session_state.root_task),
            format_func=lambda x: x[1],
            key="parent_task_select"
        )
        new_task_name = st.text_input("任务名称")
        new_task_desc = st.text_area("任务描述")
        if st.button("添加任务"):
            if new_task_name:
                parent_task = st.session_state.root_task.find_task_by_id(parent_task_id[0])
                if parent_task:
                    parent_task.add_child(new_task_name, new_task_desc)
                    st.success(f"已添加子任务 '{new_task_name}'")
                else:
                    st.error("找不到父任务")
            else:
                st.warning("请输入任务名称")
    
    # 主界面 - 显示和编辑任务
    st.header("任务树")
    
    # 递归渲染任务树
    def render_task(task, level=0):
        col1, col2, col3 = st.columns([0.1, 0.7, 0.2])
        
        with col1:
            if not task.children:  # 只有叶子节点可以勾选
                checked = st.checkbox(
                    "",
                    value=task.is_completed,
                    key=f"check_{task.task_id}",
                    on_change=lambda: set_task_completed(task.task_id, not task.is_completed)
                )
            else:
                st.write("✓" if task.is_completed else "✗")
        
        with col2:
            if st.session_state.editing_task_id == task.task_id:
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
                st.markdown(f"**{task.name}**")
                if task.description:
                    st.caption(task.description)
        
        with col3:
            if st.button("编辑", key=f"btn_edit_{task.task_id}"):
                st.session_state.editing_task_id = task.task_id
                st.experimental_rerun()
            if st.button("删除", key=f"btn_del_{task.task_id}"):
                if task.parent:
                    task.parent.remove_child(task)
                    st.experimental_rerun()
                else:
                    st.warning("不能删除根任务")
        
        # 渲染子任务
        for child in task.children:
            render_task(child, level + 1)
    
    render_task(st.session_state.root_task)
    
    # 导出/导入功能
    st.divider()
    st.header("数据管理")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("导出任务数据"):
            data = st.session_state.root_task.to_dict()
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
                st.session_state.root_task = TaskNode.from_dict(data)
                st.success("任务数据导入成功！")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"导入失败: {str(e)}")


if __name__ == "__main__":
    main()