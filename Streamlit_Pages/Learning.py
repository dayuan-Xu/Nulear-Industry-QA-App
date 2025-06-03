import streamlit as st
import numpy as np
import pandas as pd
st.header("部件1：滑块slider(拉动引起rerun):")
#每个组件的函数调用（如 st.slider(), st.text_input() 等）都有一个返回值。
#在用户与它们交互之前，在第一次调用时返回其默认值，默认值都是简单的python类型。
#在交互发生后、rerun之前，Streamlit后端会根据用户交互，更新组件在session_state中的值，
# 如果有回调函数，就先执行回调函数
#之后rerun时该组件函数返回的就是最新值，可以赋予需要的变量,比如下面的x
x = st.slider('x')  # 👈 this is a widget
st.write(x, 'squared is', x * x)

st.header("部件2：单行文本输入框text_input(Enter后会引起rerun):")

if "name" not in st.session_state:
    st.session_state.name = ""
def store_value():
    # 将最新值保存到session_state对应的长久key中
    st.session_state["name"] = st.session_state["_name"]

# 将之前保存的值赋值给短期key，实现页面切换之间保留该组件的之前状态。
# 因为页面page切换时，先是离开了该组件，此时该组件的key和关联的值会被删除，之后又回到该组件所在的页面，此时session_state不含该组件的key和关联值。
st.session_state["_name"] = st.session_state["name"]
st.text_input("请输入文本:", key="_name",icon="🔥",on_change=store_value,placeholder="引导用户输入的占位符文本")

# 指定了key的部件会自动加入session_state并可以在session_state中通过key的值来访问:
"在此处输出上面那个输入框的输入值:"+st.session_state.name

st.header("部件3：复选框checkbox（勾选--》rerun）:")
if st.checkbox('Show dataframe',  key="first_checkbox_return"):
    chart_data = pd.DataFrame(
       np.random.randn(20, 3),
       columns=['a', 'b', 'c'])

    chart_data
"Show dataframe复选框当前的勾选状态:"+("勾选" if st.session_state.first_checkbox_return else "未勾选")

st.header("部件4：下拉列表selectbox来单选(可以将选项通过数组或者dataframe列传递):")
df = pd.DataFrame({
    'first column': [1, 2, 3, 4],
    'second column': [10, 20, 30, 40]
    })

option = st.selectbox(
    'Which fruit do you like best?',
     [ "Apple", "Banana", "Orange"],index=0)

'You selected: ', option

st.header("部件5：全局的左边栏sidebar:")
# Add a selectbox to the sidebar:
add_selectbox = st.sidebar.selectbox(
    'How would you like to be contacted?',
    ('Email', 'Home phone', 'Mobile phone')
)

# Add a slider to the sidebar:
add_slider = st.sidebar.slider(
    'Select a range of values',
    0.0, 100.0, (25.0,75.0)
)
st.sidebar.write('You selected:', add_selectbox," ,", add_slider)

st.header("部件6：扩展器Expander隐藏大型内容，节省空间:")
with st.expander("See more"):
    st.write("Some very interesting things about the data.")


st.header("部件7：使用Columns来并排放置Button和单选按钮组radio:")
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

st.header("部件8：进度条progress:")

import time

if st.button('点击开始一个长期计算任务...'):

    # Add a placeholder空容器，可以在后续用 .text()、.write()、.markdown() 等方法动态更新内容
    latest_iteration = st.empty()
    # 初始化一个进度条
    bar = st.progress(0)

    for i in range(100):
      # Update the progress bar with each iteration.
      latest_iteration.text(f'Iteration {i+1}')
      bar.progress(i + 1)
      time.sleep(0.1)

    '...长期计算任务结束'


if "counter" not in st.session_state:
    st.session_state.counter = 0

st.session_state.counter += 1
with st.sidebar:
    st.header(f"This page has run {st.session_state.counter} times.")
st.button("Run it again")



import datetime
st.title('Counter Example:不仅实现计数，还存储更新的时间')
if 'count' not in st.session_state:
    st.session_state.count = 0
    st.session_state.last_updated = datetime.time(0,0)

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


value=st.button("一个带key的按钮，它在初次加载时默认返回Flase，True值仅仅维持于单次运行中",key="button_with_key")
"带key按钮的值为:"
st.write("通过session_state访问：", st.session_state.button_with_key)

st.title("需要键盘输入的控件，当用户点击其他地方或使用 Tab 键离开控件时，新的输入值会触发脚本重新运行。(而旧的输入值不会)\
此外，用户也可以在控件中按下 Enter 键 来立即提交更改，从而触发脚本重运行")
st.number_input("请输入数字:", key="number")
st.text_input("请输入文本:", key="text", value="该单行文本输入框的默认值，仅仅在首次加载，没有接受交互时显示",icon="🔥")
st.text_area("请输入多行文本:", key="text_area",value="该多行文本输入框的默认值，仅仅在首次加载，没有接受交互时显示")

st.title("表单内部的所有控件（widget）在初次加载时显示默认值，通过value参数设置，而在提交后重新运行脚本时会保留用户之前输入的值")
with st.form("form0"):
    name = st.text_input("名字", value="张三")
    age = st.slider("年龄", 0, 100, 25)
    submitted = st.form_submit_button("提交")

if submitted:
    st.write(f"你输入的名字是：{name}，年龄是：{age}")
else:
    st.write("表单尚未提交，显示的是默认值。")

st.title("表单内部widget的值在提交时才会在session_state中发生更新，当用户点击提交按钮时，若设置了回调函数，回调函数中可以通过session_state获取表单内指定了key的widget的最新提交的值")
col1,col2=st.columns(2)
col1.title("Sum:")
def sum():
    col2.title(st.session_state.number1+st.session_state.number2)
with st.form("form1"):
    number1=st.number_input("请输入数字:", key="number1")
    number2=st.number_input("请输入数字:", key="number2")
    # 下面错误使用args传递表单内部widget的值，但是传递的其实会是旧值，而不是用户输入的最新值
    #submitted = st.form_submit_button("提交", on_click=sum,args=(number1,number2))
    # 正确写法,是在回调函数sum中通过session_state获取表单内指定key的widget的值，这些才是表单提交时被保存的的最新值。
    submitted = st.form_submit_button("提交",on_click=sum)
