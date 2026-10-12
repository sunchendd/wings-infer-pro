# G.OPR.01 对除法运算和模运算中的除数为0的情况做相应保护

- **规则ID**：e38d18aa-334a-4542-9f5c-ddfb0ba8b4ed
- **更新时间**：2026-04-07 04:15:04

---

**【问题级别】**

严重

**【描述】**

如果除法或模运算中的除数为零可能会导致程序终止，因此需要对除数为0的情况做相应保护。

保护措施主要是以下三种：



在除法运算前，对除数是否为0进行判断。

通过捕获除0异常ZeroDivisionError的方式，来防止程序意外终止。

明确参数的使用约束，由调用方确保除数不为零。

**【正确示例】**

```
【正例1】
dividen_num = 0
divisor_num = 0

# 符合，在进行除法运算前，先对除数做非0判断
if divisor_num != 0:
    division_result = dividen_num / divisor_num
    remainder_result = dividen_num % divisor_num
else:
    print("You can't divide by 0!")

【正例2】
dividen_num = 0
divisor_num = 0

# 符合，通过捕获除0异常ZeroDivisionError的方式，来防止程序意外终止
try:
    division_result = dividen_num / divisor_num
except ZeroDivisionError:
    print("You can't divide by 0!")
else:
    ...

```
**【错误示例】**

```
# 下面的示例中，没有对除数进行非零判断，会导致程序运行错误。
dividen_num = 0
divisor_num = 0

division_result = dividen_num / divisor_num
remainder_result = dividen_num % divisor_num

```
**【修复建议】**

1. 在除法运算前，对除数是否为0进行判断。

2. 通过捕获除0异常ZeroDivisionError的方式，来防止程序意外终止。

3. 明确参数的使用约束，由调用方确保除数不为零。
