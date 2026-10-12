# G.FNM.07 建议妥善处理函数的返回值和异常

- **规则ID**：4e0668c9-293e-4717-9f5d-3d9874147c2b
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

一般

**【描述】**

如果函数的返回值和异常没有正常处理，可能会使程序代码逻辑混乱，可读性差，难以维护。因此，建议妥善处理函数的返回值和异常。

**【正确示例】**

```
##### 场景1：函数返回值或异常没有处理
- 修复示例：此处捕获了test可能发生的异常（即：函数调用产生的副作用）并进行了处理，属于有效代码
```python
import sys


def test(x, y):
    x, y = map(int, [x, y])
    return x / y


if __name__ == "__main__":
    try:
        test(sys.argv[1], sys.argv[2])  # 符合
    except ZeroDivisionError:
        sys.exit(1)
    sys.exit(0)
```
##### 场景2：缺少失败场景返回值的检查
- 修复示例：补充失败场景返回值检查
```python
def get_api():
    status_code = to_be_called()
    if status_code == -1:  # 符合，失败场景返回值检查
        ...
    if status_code >= 0:
        ...  
```


```
**【错误示例】**

```
##### 场景1：函数返回值或异常没有处理
- 错误示例：此处虽调用了test函数，但是未进行任何的处理，对业务结果不产生任何影响（除了执行代码时占用了极少量的CPU跟内存外）
```python
import sys


def test():
    return "121231"


if __name__ == "__main__":
    test()  # 不符合，此处虽调用了test函数，但是未进行任何的处理，对业务结果不产生任何影响
    sys.exit(0)

```
- 错误示例：示例中被调用函数存在异常场景，调用函数而不进行检查或者异常捕获处理，会存在代码报错中断的风险。
```python
import sys


def test():
    ...
    try:
        ...
    except UserDefined.UnrecoverableException as e:
        do_something(e)
        raise e  # 重新抛出异常UserDefined.UnrecoverableException


if __name__ == "__main__":
    test()  # 不符合，调用函数而不进行检查或者异常捕获处理，会存在代码报错中断的风险。
    sys.exit(0)

```
##### 场景2：缺少失败场景返回值的检查
- 错误示例：当被调用函数的api文档存在成功状态码status_code以及失败状态码-1时，未对失败状态码进行正确处理。
```python
def get_api():
    status_code = to_be_called()
    if status_code >= 0: 
        ... 
    # 不符合，缺少失败场景返回值的检查
```


```
**【修复建议】**

1. 函数返回值既未参与程序业务逻辑处理时，函数的调用也无需进行预期异常和相应返回值处理，应及时删除。

2. 当函数通常通过返回值返回数据或执行结果时，调用者应该在函数调用之后，对返回数据及执行结果进行有效、正确的合法性检查和处理。
