# G.FMT.01 程序块应该采用4个空格缩进风格编写

- **规则ID**：827ea62b-9ccb-439c-8740-42ebbe959a6d
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

一般

**【描述】**

程序块采用缩进风格编写，以4个空格为缩进单位。

选择结构、循环结构、异常处理结构、函数定义、类定义、成员方法定义、类方法定义、静态方法定义、with块等语法结构，代码块相对于头部应该有4个空格的缩 进。

相同级别的代码应具有相同的缩进量，虽然不影响程序运行，也不允许在逻辑上具有相同缩进层次的代码在视觉上具有不同的缩进量。

使用空格（space）和跳格（Tab），虽然视觉效果一样，但禁止在缩进时混合使用跳格和空格，否则程序无法运行，提示错误’SyntaxError: inconsistent use of tabs and spaces in indentation’。

**【正确示例】**

```
# 【正例1】
for key, value in x_dict.items():
    if value < 100:
        print('value小于100')
    elif value > 100:
        print('value大于100')
    else:
        print('value等于100')

# 【正例2】
number = input('Input an integer:')

if number == '0':
    print('输入的0。')
else:
    print('输入的不是0。')       # 符合，相同级别的代码具有相同的缩进量

```
**【错误示例】**

```
```python

```
**【修复建议】**

程序块采用缩进风格编写，以4个空格为缩进单位
