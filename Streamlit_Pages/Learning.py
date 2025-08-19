import time
import threading
import numpy as np
import pandas as pd
import streamlit as st
from streamlit.runtime.scriptrunner_utils.script_run_context import add_script_run_ctx, get_script_run_ctx
if "progress" not in st.session_state:
    st.session_state.progress = {}
top_menu=st.tabs(["**1 使用fragment检查更新后台任务进度**","fragment2","fragment3"])
def update_progress(name):
    st.session_state.progress[name] = 0
    for i in range(100):
        time.sleep(0.1)  # 模拟一些处理时间
        st.session_state.progress[name] += 1  # 修改session中的变量
        print(f"{name}线程更新了进度为 {st.session_state.progress[name]}")
    print(f"更新session中的进度变量的{name}线程结束")
    del st.session_state.progress[name]


with top_menu[0]:
    with st.container(border=True):
        st.subheader("原理:一个fragment的rerun独立于其他fragment和整个脚本，所以可以把检查后台线程执行进度并显示的工作交给一个fragmen函数")
        if st.button("开启一个后台解析线程"):
            name="张三"
            thread = threading.Thread(target=update_progress,args=(name,))
            add_script_run_ctx(thread, get_script_run_ctx())
            thread.start()

        if st.button("开启另一个后台解析线程"):
            name="李四"
            thread = threading.Thread(target=update_progress,args=(name,))
            add_script_run_ctx(thread, get_script_run_ctx())
            thread.start()

        @st.fragment(run_every=0.5)
        def show_progress():
            for key, value in st.session_state.progress.items():
                st.progress(value, f"{key}线程的当前进度:{value}")
        "下面调用一个fragment函数统一检查并显示所有后台任务的最新进度"
        show_progress()

        st.subheader("下面是其他的组件，他们在用户开启上述的两个后台线程时仍然可以响应用户交互")

        on = st.toggle("一个开关,属于普通脚本",key="toggle2")
        if on:
            "开关打开，这句话才显示！"

@st.fragment
def show_demo1():
    st.markdown("#### 示例1：开启多个线程，一直等待，直到所有线程结束后，再加载显示它们的返回结果")
    class WorkerThread(threading.Thread):
        def __init__(self, delay):
            super().__init__()
            self.delay = delay
            self.return_value = None

        def run(self):
            start_time = time.time()
            time.sleep(self.delay)
            end_time = time.time()
            self.return_value = f"start: {start_time}, end: {end_time}"

    delays = [5, 4, 3, 2, 1]
    if st.button("Run it 1"):
        threads = [WorkerThread(delay) for delay in delays]
        for thread in threads:
            thread.start()
        # 等待每个线程都执行完，再执行结果显示
        for thread in threads:
            thread.join()
        st.header("如果当前脚本阻塞于等待所有子线程执行结束，那么这句话会与所有子线程结果一同显现！")
        for i, thread in enumerate(threads):
            st.header(f"Thread {i}")
            st.write(thread.return_value)

@st.fragment
def show_demo2():
    st.markdown("#### 示例2：先创建占位容器，再开启多个线程，每0.5s检查是否有线程结束并把其返回值写到对应容器。")
    class WorkerThread2(threading.Thread):
        def __init__(self, delay):
            super().__init__()
            self.delay = delay
            self.return_value = None

        def run(self):
            start_time = time.time()
            time.sleep(self.delay)
            end_time = time.time()
            self.return_value = f"start: {start_time}, end: {end_time}"

    delays = [5, 4, 3, 2, 1]
    result_containers = []
    if st.button("Run it 2"):
        for i, delay in enumerate(delays):
            st.header(f"Thread {i}")
            # 创建占位容器
            result_containers.append(st.container())
        threads = [WorkerThread2(delay) for delay in delays]
        # 启动所有线程
        for thread in threads:
            thread.start()
        thread_lives = [True] * len(threads)
        while any(thread_lives):
            # 只有有一个线程存活，就每隔0.5s检查所有线程对象
            for i, thread in enumerate(threads):
                if thread_lives[i] and not thread.is_alive():
                    result_containers[i].write(thread.return_value)
                    # 下次不再检查它是否结束
                    thread_lives[i] = False
            time.sleep(0.5)
        st.header(
            "如果当前脚本阻塞于检查存活的子线程直至所有子线程都执行结束，那么这句话的开启按钮只会在最后一个子线程结果显示才出现！")

@st.fragment
def show_demo3():
    st.markdown("### Case2：开启多个线程，并且要在线程内部使用st命令")
    st.markdown("#### 唯一示例：线程运行时，使用了st命令往指定容器内添加小组件，"
                "脚本中在启动线程前为之添加了脚本运行上下文，并且在脚本中逐个子线程使用join命令确保其结束")
    from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
    class WorkerThread3(threading.Thread):
        def __init__(self, delay, target):
            super().__init__()
            self.delay = delay
            self.target = target

        def run(self):
            # 向目标容器内写入组件
            start_time = time.time()
            time.sleep(self.delay)
            end_time = time.time()
            self.target.write(f"start: {start_time}, end: {end_time}")

    if st.button("Run this demo"):
        delays = [5, 4, 3, 2, 1]
        result_containers = []
        # 先创建占位容器
        for i, delay in enumerate(delays):
            st.header(f"Thread {i}")
            result_containers.append(st.container())

        threads = [WorkerThread3(delay, container) for delay, container in zip(delays, result_containers)]
        # 先为线程添加当前脚本运行上下文，再启动线程
        for thread in threads:
            add_script_run_ctx(thread, get_script_run_ctx())
            thread.start()
        # 逐个等待所有线程结束，这确保了子线程不会在当前脚本运行线程结束后还存活着
        for thread in threads:
            thread.join()
        st.header("如果当前脚本阻塞于检查存活的子线程直至所有子线程都执行结束，那么这句话只会在最后一个子线程结果显示后才出现！")

def how_to_use_slider():
    st.subheader("部件5：全局的左边栏sidebar")
    # 添加单选框
    add_selectbox = st.sidebar.selectbox(
        '选择一个联系方式',
        ('Email', 'Home phone', 'Mobile phone')
    )

    # 滑动器
    add_slider = st.sidebar.slider(
        '选择一个数值范围',
        0.0, 100.0, (25.0, 75.0)
    )
    st.sidebar.write('你的选择:', add_selectbox, " ,", add_slider)
@st.fragment
def show_common_widgets():
    st.subheader("部件1：滑动器slider(拉动引起rerun):")
    # 每个组件的函数调用（如 st.slider(), st.text_input() 等）都有一个返回值。
    # 在用户与它们交互之前，在第一次调用时返回其默认值，默认值都是简单的python类型。
    # 在交互发生后、rerun之前，Streamlit后端会根据用户交互，更新组件在session_state中的值，
    # 如果有回调函数，就先执行回调函数
    # 之后rerun时该组件函数返回的就是最新值，可以赋予需要的变量,比如下面的x
    x = st.slider('x')  # 👈 this is a widget
    st.write(x, 'squared is', x * x)

    st.subheader("部件2：单行文本输入框text_input(Enter后会引起rerun):")

    if "name" not in st.session_state:
        st.session_state.name = ""

    def store_value():
        # 将最新值保存到session_state对应的长久key中
        st.session_state["name"] = st.session_state["_name"]

    # 将之前保存的值赋值给短期key，实现页面切换之间保留该组件的之前状态。
    # 因为页面page切换时，先是离开了该组件，此时该组件的key和关联的值会被删除，之后又回到该组件所在的页面，此时session_state不含该组件的key和关联值。
    st.session_state["_name"] = st.session_state["name"]
    st.text_input("请输入文本:", key="_name", icon="🔥", on_change=store_value, placeholder="引导用户输入的占位符文本")

    # 指定了key的部件会自动加入session_state并可以在session_state中通过key的值来访问:
    "在此处输出上面那个输入框的输入值:" + st.session_state.name

    st.subheader("部件3：复选框checkbox（勾选导致rerun）:")
    if st.checkbox('Show dataframe', key="first_checkbox_return"):
        chart_data = pd.DataFrame(
            np.random.randn(20, 3),
            columns=['a', 'b', 'c'])

        chart_data
    "Show dataframe复选框当前的勾选状态:" + ("勾选" if st.session_state.first_checkbox_return else "未勾选")

    st.subheader("部件4：下拉列表selectbox来单选(可以将选项通过数组或者dataframe列传递):")
    df = pd.DataFrame({
        'first column': [1, 2, 3, 4],
        'second column': [10, 20, 30, 40]
    })

    option = st.selectbox(
        'Which fruit do you like best?',
        ["Apple", "Banana", "Orange"], index=0)

    'You selected: ', option

    st.subheader("部件6：扩张器Expander隐藏大型内容，节省空间:")
    with st.expander("Expander"):
        st.write("这个扩展器内的内容")

    st.subheader("部件7：使用Columns来并排放置Button和单选按钮组radio:")
    left_column, right_column = st.columns(2)
    # You can use a column just like st.sidebar:
    left_column.button('Button')

    # Or even better, call Streamlit functions inside a "with" block:
    with right_column:
        chosen1 = st.radio(
            '选项（只能单选）',
            ("A、OS", "B、计网", "C、数据结构", "D、计组"))
        st.write(f"你选择了 {chosen1} ")

        chosen2 = st.radio('选项（只能单选）',
                           ("A、软工", "B、统计学习方法", "C、数据结构", "D、计组"))
        st.write(f"你选择了 {chosen2} ")

    st.subheader("部件8：进度条progress:")

    import time
    if st.button('点击开始一个长期计算任务...'):
        # 初始化一个进度条
        bar = st.progress(0)
        for i in range(100):
            bar.progress(i + 1,f'Iteration {i + 1}')
            time.sleep(0.025)
        '长期计算任务结束'
    st.subheader("部件9：开关toggle:")
    on1=st.toggle("Show a sentence",key="toggle_demo")
    if on1:
        "开关打开，这句话才显示！"

@st.fragment
def show_form():
    import datetime
    st.subheader('Counter Example:不仅实现计数，还存储更新的时间')
    if 'count' not in st.session_state:
        st.session_state.count = 0
        st.session_state.last_updated = datetime.time(0, 0)

    def update_counter():
        # 回调函数中可以之间通过session_state获取制定了key的widget的值。
        st.session_state.count += st.session_state.increment_value
        st.session_state.last_updated = st.session_state.update_time

    with st.form(key='my_form'):
        st.time_input(label='Enter the time', value=datetime.datetime.now().time(), key='update_time')
        st.number_input('Enter a value', value=0, step=1, key='increment_value')
        submit = st.form_submit_button(label='Update', on_click=update_counter)

    st.write('Current Count = ', st.session_state.count)
    st.write('Last Updated = ', st.session_state.last_updated)

@st.fragment
def show_widget_behavior():
    st.subheader("需要键盘输入的控件，当用户点击其他地方或使用 Tab 键离开控件时，新的输入值会触发脚本重新运行。(而旧的输入值不会)\
        此外，用户也可以在控件中按下 Enter 键 来立即提交更改，从而触发脚本重运行")
    st.number_input("请输入数字:", key="number")
    st.text_input("请输入文本:", key="text", value="该单行文本输入框的默认值，仅仅在首次加载，没有接受交互时显示",
                  icon="🔥")
    st.text_area("请输入多行文本:", key="text_area", value="该多行文本输入框的默认值，仅仅在首次加载，没有接受交互时显示")

    st.subheader(
        "表单内部的所有控件（widget）在初次加载时显示通过value参数设置的默认值，而在提交后重新运行脚本加载时会保留用户之前输入的值")
    with st.form("form0"):
        name = st.text_input("名字", value="张三")
        age = st.slider("年龄", 0, 100, 25)
        submitted = st.form_submit_button("提交")

    if submitted:
        st.write(f"你输入的名字是：{name}，年龄是：{age}")
    else:
        st.write("表单尚未提交，显示的是默认值。")

    st.subheader(
        "表单内部widget的值在提交时才会在session_state中发生更新，当用户点击提交按钮时，若设置了回调函数，回调函数中可以通过session_state获取表单内指定了key的widget的最新提交的值")
    col1, col2 = st.columns(2)
    col1.subheader("Sum:")

    def sum():
        col2.subheader(st.session_state.number1 + st.session_state.number2)

    with st.form("form1"):
        number1 = st.number_input("请输入数字:", key="number1")
        number2 = st.number_input("请输入数字:", key="number2")
        # 下面错误使用args传递表单内部widget的值，但是传递的其实会是旧值，而不是用户输入的最新值
        # submitted = st.form_submit_button("提交", on_click=sum,args=(number1,number2))
        # 正确写法,是在回调函数sum中通过session_state获取表单内指定key的widget的值，这些才是表单提交时被保存的的最新值。
        submitted = st.form_submit_button("提交", on_click=sum)

@st.fragment
def show_button_usecases():
    st.header("按钮要么显示一次性的消息、要么用来保存数据到session_state或文件、DB中")
    value = st.button("一个带key的按钮，它在初次加载时默认返回Flase，True值仅仅维持于单次运行中", key="button_with_key")
    "带key按钮的值为:"
    st.write("通过session_state访问：", st.session_state.button_with_key)
    st.markdown("#### 用例1：点击按钮检查输入的合法性")
    animal_shelter = ['cat', 'dog', 'rabbit', 'bird']

    animal = st.text_input('Type an animal')

    if st.button('Check availability'):
        have_it = animal.lower() in animal_shelter
        'We have that animal!' if have_it else 'We don\'t have that animal.'

    st.markdown("#### 用例2：通过session_state来记住某个按钮曾经是否被点击过，并保持记忆")

    if 'clicked' not in st.session_state:
        st.session_state.clicked = False

    def click_button():
        st.session_state.clicked = True

    st.button('Click me1', on_click=click_button)

    if st.session_state.clicked:
        # The message and nested widget will remain on the page
        st.write('Button clicked!')
        st.slider('Select a value')

    st.markdown("#### 用例3：按钮+session_state，实现开关toggle的功能，控制其他小组件的持续呈现或者关闭")
    if 'button' not in st.session_state:
        st.session_state.button = False

    def click_button():
        st.session_state.button = not st.session_state.button

    st.button('滑动器展示开关', on_click=click_button)
    if st.session_state.button:
        # The message and nested widget will remain on the page
        st.write('开关处于打开状态!')
        st.slider('Select a value2')
    else:
        st.write('开关关上了!')

    if 'stage' not in st.session_state:
        st.session_state.stage = 0

    st.markdown("#### 用例4：使用按钮+session_state实现控制流")

    def set_state(i):
        st.session_state.stage = i

    if st.session_state.stage == 0:
        st.button('Begin', on_click=set_state, args=[1])

    if st.session_state.stage >= 1:
        name = st.text_input('Name', on_change=set_state, args=[2])

    if st.session_state.stage >= 2:
        st.write(f'Hello {name}!')
        color = st.selectbox(
            'Pick a Color',
            [None, 'red', 'orange', 'green', 'blue', 'violet'],
            on_change=set_state, args=[3]
        )
        if color is None:
            set_state(2)

    if st.session_state.stage >= 3:
        st.write(f':{color}[Thank you!]')
        st.button('Start Over', on_click=set_state, args=[0])
    st.markdown("#### 用例5：按钮+回调，用于修改或重置其他小组件")
    st.text_input('Name', key='name')

    def set_name(name):
        st.session_state.name = name

    st.button('Clear name', on_click=set_name, args=[''])
    st.button('Streamlit!', on_click=set_name, args=['Streamlit'])

    st.markdown("#### 用例6：使用按钮动态添加小组件，确保key不要重复")

    def display_input_row(index):
        left, middle, right = st.columns(3)
        left.text_input('First', key=f'first_{index}')
        middle.text_input('Middle', key=f'middle_{index}')
        right.text_input('Last', key=f'last_{index}')

    if 'rows' not in st.session_state:
        st.session_state['rows'] = 0

    def increase_rows():
        st.session_state['rows'] += 1

    st.button('Add person', on_click=increase_rows)

    for i in range(st.session_state['rows']):
        display_input_row(i)

    # Show the results
    st.subheader('People')
    for i in range(st.session_state['rows']):
        st.write(
            f'Person {i + 1}:',
            st.session_state[f'first_{i}'],
            st.session_state[f'middle_{i}'],
            st.session_state[f'last_{i}']
        )

    st.markdown("#### 用例7：点击按钮，以运行高代价或文件写入的流程，并保存结果到session_state中，以便下次直接利用已有结果")

    import pandas as pd
    import time
    def expensive_process(option, add):
        # 模拟耗时操作，可以根据入参从session_state中尝试获取之前已经存储的执行结果。
        with st.spinner('Processing...'):
            time.sleep(5)
        df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6], 'C': [7, 8, 9]}) + add
        return (df, add)

    cols = st.columns(2)
    option = cols[0].selectbox('Select a number', options=['1', '2', '3'])
    add = cols[1].number_input('Add a number', min_value=0, max_value=10)

    if 'processed' not in st.session_state:
        st.session_state.processed = {}

    # Process and save results
    if st.button('Process'):
        result = expensive_process(option, add)
        st.session_state.processed[option] = result
        st.write(f'Option {option} processed with add {add}')
        result[0]

    st.markdown("#### 用例8：按钮触发的fragment函数")

    @st.fragment
    def fragment():
        st.write("This is a fragment")
        if st.button("Click me"):
            st.rerun()

    if st.button("点击按钮，触发fragment函数"):
        st.write("点击了按钮，现在触发fragment函数")
        fragment()

""
""
""
""
""
""
""
""
""
""
""
""
""
""
""
st.subheader("与fragment内部组件交互只会导致该fragment内部rerun，不会导致整个脚本文件rerun，下面的标签页中的组件大都使用一个fragment函数加载的")

tabs=st.tabs(["**1、常见小组件**", "**2、表单**", "**3、小组件行为**","**4、按钮**","**5、多线程**","**6、yield与spinner**","**7、状态提示组件**"])
with tabs[0]:
    how_to_use_slider()
    show_common_widgets()
with tabs[1]:
    show_form()
with tabs[2]:
    show_widget_behavior()
with tabs[3]:
    show_button_usecases()
with tabs[4]:
    with st.container(border= True):
        st.markdown("### Case1：线程内部没有使用st命令加载小组件（推荐做法，能完全避免与Streamlit服务器冲突）")
        show_demo1()
        show_demo2()
    with st.container(border=True):
        show_demo3()

with tabs[5]:
    @st.fragment
    def show_spinner():
        if st.button("Run demo1"):
            # 定义一个生产器，每3秒生产一个数字
            def slow_generator():
                for i in range(2):
                    with st.spinner(f'正在生成第 {i + 1} 个数字...'):
                        time.sleep(1.5)  # 等待3秒
                    yield i
            # 遍历该生成器，并使用spinner显示正在加载
            for i in slow_generator():
                st.header(i)
        if st.button("Run demo2"):
            # 将加载操作包含进spinner的上下文,在操作进行时就一直显示圈圈，操作结束时圈圈消失。
            with st.spinner('正在连续生成2个数字...'):
                for i in range(3, 5):
                    st.header(i)
                    time.sleep(1.5)
    show_spinner()

with tabs[6]:
    @st.fragment
    def how_to_show_info():
        st.info("这是一条普通信息")
        st.success("这是一条成功信息")
        st.warning("这是一条警告信息")
        st.error("这是一条错误信息")
        if st.button("Run roast demo"):
            st.toast("这是一条短暂停留的提示信息",icon="✅")# 默认成功
            time.sleep(0.5)
            st.toast("这是一条短暂停留的提示信息",icon="ℹ️")# 提示
            time.sleep(0.5)
            st.toast("这是一条短暂停留的提示信息",icon="⚠️")# 警告
            time.sleep(0.5)
            st.toast("这是一条短暂停留的提示信息",icon="🚨")# 错误
    how_to_show_info()





