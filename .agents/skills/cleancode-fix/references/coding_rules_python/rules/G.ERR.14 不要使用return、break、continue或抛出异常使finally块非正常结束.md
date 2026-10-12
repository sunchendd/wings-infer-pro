# G.ERR.14 不要使用return、break、continue或抛出异常使finally块非正常结束

- **规则ID**：63c7b433-086f-4874-a641-276771c56e9e
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

严重

**【描述】**

在finally代码块中，由于直接使用return语句，或者由于调用方法的异常未处理，会导致finally代码块无法正常结束。



非正常结束的finally代码块会影响try或catch代码块中异常的抛出，也可能会影响函数或方法的返回值。

**【正确示例】**

```
##### 场景1：finally里出现return语句
- 修复示例：正确处理try代码块中可能产生的异常，不要在finally代码块中出现return语句
```python
def control_statement_in_finally(param):
    ret = -1
    try:
        ret = 1 / param
    except ZeroDivisionError:
        do_something()
    finally:
        # 符合
        do_finally()
    return ret
```
##### 场景2：finally语句非正常结束
- 修复示例：判断文件是否关闭，确保finally正常结束
```python
fp = None
try:
    fp = open('test_read.txt', encoding='utf8')
    print(fp.read())
except FileNotFoundError:
    print('文件不存在')
except UnicodeDecodeError:
    print('编码格式错误')
finally:
    if fp:   # 符合，关闭文件之前，增加判断，避免异常
        fp.close()
```

```
**【错误示例】**

```
##### 场景1：finally里出现return语句
- 错误示例：finally里的return语句会导致param为0时也不会抛出ZeroDivisionError异常

```python

def control_statement_in_finally(param):

    ret = -1

    try:

        ret = 1 / param

    finally:

        # 不符合，finnaly出现return语句

        return ret  

```
##### 场景2：finally语句非正常结束
- 错误示例：使用finally来确保文件被关闭，但文件不存在时使finally子句中的代码引发了异常，不能正常结束

```python

try:

    fp = open('test_read.txt', encoding='utf8')

    print(fp.read())

except FileNotFoundError:

    print('文件不存在')

except UnicodeDecodeError:

    print('编码格式错误')

finally:

    # 不符合，非正常结束

    fp.close()



Traceback (most recent call last):

 File "<pyshell#130>", line 9, in <module>

 fp.close()

NameError: name 'fp' is not defined

```

```
**【修复建议】**

finnaly语句应该做try-except语句正常结束的代码总处理。
