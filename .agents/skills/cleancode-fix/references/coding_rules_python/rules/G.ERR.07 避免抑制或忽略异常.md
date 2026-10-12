# G.ERR.07 避免抑制或忽略异常

- **规则ID**：b4f5aadd-8604-4dbe-87f5-f3b74eebe5bf
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

一般

**【描述】**

当一段代码可能发生异常时，需要明确对这些异常的处理策略，包括但不限于重置状态、填充默认值、重试、返回错误等。

编码时应尽量避免捕获一个异常但什么都不做的情况，抑制或忽略异常很可能丢掉关键的错误和应对，对程序的稳定运行产生风险。

**【正确示例】**

```
【正例1】捕获异常，并对异常做出相应的处理。
try:
    ...
except CertainException as e:
    log_something(e)
    do_something(e)

【正例2】捕获异常，并给出错误信息和提示。
def get_input_password():
    while True:
        try:
            password = input('Please enter password: ')
            check_complexity(password)
        except UserDefined.ComplexityMismatch:
            print('Password must contain 8 or more characters with a mix of letters, numbers & symbols')
            continue
        try:
            repeat_password = input('Please repeat password and enter: ')
            check_consistency(password, repeat_password)
            break
        except UserDefined.ConsistencyMismatch:
            print('Passwords didn’t match. Try again.')

    return password

```
**【错误示例】**

```
【反例1】
try:
    ...
except CertainException:  # 没有对异常做出相应的处理，存在风险
    pass

【反例2】
def get_input_integer():
    while True:
        try:
            i = input('Please enter an integer: ')
            check_integer(i)
        except ValueError:
            pass  # 这里看似合理，实际上在捕获异常后需要给用户足够的错误信息

    return i

【例外】
如果业务场景需要忽略某些异常，并且这些异常不需要做日志记录，此时应增加注释说明忽略的理由。

```
**【修复建议】**

捕获异常，并对异常做出相应的处理。
