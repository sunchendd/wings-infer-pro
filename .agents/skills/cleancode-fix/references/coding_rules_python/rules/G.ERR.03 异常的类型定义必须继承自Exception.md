# G.ERR.03 异常的类型定义必须继承自Exception

- **规则ID**：8cfa249c-48b8-499f-9cbc-bf54f9042a0a
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

严重

**【描述】**

自定义的异常类型必须继承自`Exception`，按照`已知异常->Exception`的顺序捕获时，不需要关注对键盘中断、进程退出、生成器结束等异常的特殊处理。

禁止使用非异常类型作为`raise`对象，如`NotImplemented`、可迭代对象等，否则会导致无法正确抛出异常。

**【正确示例】**

```
##### 场景1：异常继承
- 修复示例：异常继承自Exception。
```python
# 符合，异常类继承自Exception
class AuthenticationError(Exception):
    def __init__(self, message=None):
        super(AuthenticationError, self).__init__(message)
        self.http_code = 404


def handle_request(req):
    try:
        ...
    except AuthenticationError as e:
        return Response(e.http_code, e.message)
    except Exception as e:
        return Response(400, e.message)
```

```
**【错误示例】**

```
##### 场景1：异常继承
- 错误示例：异常继承自BaseException。
```python
# 不符合，异常类继承自BaseException
class AuthenticationError(BaseException):
    def __init__(self, message=None):
        super(AuthenticationError, self).__init__(message)
        self.http_code = 404


def handle_request(req):
    try:
        ...
    # 对中断做例外处理，因为异常继承自BaseException，若不做例外处理，则会因为中断导致覆盖AuthenticationError，最终被BaseException捕获
    except (KeyboardInterrupt, SystemExit):
        raise
    except AuthenticationError as e:
        return Response(e.http_code, e.message)
    except BaseException as e:  # 不建议使用BaseException作为最终的异常捕获类型
        return Response(400, e.message)
```

```
**【修复建议】**

异常类必须继承自Exception，不能是BaseException。
