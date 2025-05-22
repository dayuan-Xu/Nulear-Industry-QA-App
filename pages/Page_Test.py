import streamlit as st
import numpy as np
import pandas as pd

st.header("部件1：滑块(拉动引起rerun):")
#每个组件（如 st.slider, st.text_input 等）都有一个返回值。
#在 rerun 时，Streamlit 会根据用户的最新输入或选择，将对应值赋给变量,比如下面的x
x = st.slider('x')  # 👈 this is a widget
st.write(x, 'squared is', x * x)

st.header("部件2：文本输入框(Enter后会引起rerun):")
st.text_input("请输入文本:", key="name", value="",icon="🔥")

# 指定了key的部件会自动加入session_state并可以在session_state中通过key的值来访问:
"在此处输出上面那个输入框的输入值:"+st.session_state.name

st.header("部件3：复选框（勾选--》rerun）:")
if st.checkbox('Show dataframe',  key="first_checkbox_return"):
    chart_data = pd.DataFrame(
       np.random.randn(20, 3),
       columns=['a', 'b', 'c'])

    chart_data
"Show dataframe复选框当前的勾选状态:"+("勾选" if st.session_state.first_checkbox_return else "未勾选")

st.header("部件4：下拉列表来单选(可以将选项通过数组或者dataframe列传递):")
df = pd.DataFrame({
    'first column': [1, 2, 3, 4],
    'second column': [10, 20, 30, 40]
    })

option = st.selectbox(
    'Which fruit do you like best?',
     [ "Apple", "Banana", "Orange"],index=0)

'You selected: ', option

st.header("部件5：左边栏:")
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


st.header("部件7：通过Columns来并排放置:")
left_column, right_column = st.columns(2)
# You can use a column just like st.sidebar:
left_column.button('Press me!')

# Or even better, call Streamlit functions inside a "with" block:
with right_column:
    chosen1 = st.radio(
        '选项（只能单选）',
        ("A、OS", "B、计网", "C、数据结构", "D、计组"))
    st.write(f"你选择了 {chosen1} ")

    chosen2 = st.radio('选项（只能单选）',
    ("A、软工", "B、统计学习方法", "C、数据结构", "D、计组"))
    st.write(f"你选择了 {chosen2} ")

st.header("部件8：进度条:")

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

st.header(f"This page has run {st.session_state.counter} times.")
st.button("Run it again")



import datetime
st.title('Counter Example')
if 'count' not in st.session_state:
    st.session_state.count = 0
    st.session_state.last_updated = datetime.time(0,0)

def update_counter():
    st.session_state.count += st.session_state.increment_value
    st.session_state.last_updated = st.session_state.update_time

with st.form(key='my_form'):
    st.time_input(label='Enter the time', value=datetime.datetime.now().time(), key='update_time')
    st.number_input('Enter a value', value=0, step=1, key='increment_value')
    submit = st.form_submit_button(label='Update', on_click=update_counter)

st.write('Current Count = ', st.session_state.count)
st.write('Last Updated = ', st.session_state.last_updated)
