# G.CTL.01 同一个函数所有分支的返回值类型和个数保持一致(试用)

- **规则ID**：55064323-2081-4c56-b29d-34a981701f6b
- **更新时间**：2025-06-05 04:15:00

---

**【问题级别】**

严重

**【描述】**

Python的函数/方法没有显式的返回语句return时，会默认返回None。如果一个函数/方法的多个分支有的使用显式return语句，有的不使用显式return，那么对于调用者来说就无法使用一个统一的类型来处理这个函数的返回对象，可能在返回对象的后续处理过程中发生错误。

因此，要求函数/方法要么所有分支都显式地使用return语句，要么所有分支都隐式地不使用return语句，即默认返回None。

**【正确示例】**

```
# 【正例1】
INVALID_VALUE = -1


def function_with_return_statement(x):
    if x >= 0:
        return x + 1
    else:
        return INVALID_VALUE  


def function_return_type_consistent(x):
    if x < 0:
        return INVALID_VALUE  
    return x + 1

# 【正例2】可以使用类型注解，显式地提示出函数/方法预期的返回对象类型。需要注意的是，类型注解并不真正检查返回值类型和参数类型，只是一种预期。
INVALID_VALUE = -1

def function_with_return_statement(x: int) -> int:
    if x >= 0:
        return x + 1
    else:
        return INVALID_VALUE 


def function_return_type_consistent(x: int) -> int:
    if x < 0:
        return INVALID_VALUE 
    return x + 1

```
**【错误示例】**

```
# 【反例1】下面的函数都包含if条件分支，但多分支的返回对象类型不一致
def function_with_no_else_return_statement(x):
    if x >= 0:
        return x + 1


def function_return_type_inconsistent(x):
    if x < 0:
        return
    return  x + 1

```
**【修复建议】**

同一个函数所有分支的返回值类型和个数保持一致。
