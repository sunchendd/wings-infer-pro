# G.PRE.05 函数式宏定义中慎用 return、goto、continue、break 等改变程序流程的语句

- **规则ID**：b0c09279-9e95-4c18-8d74-ecc275cb1c39
- **更新时间**：2025-03-25 19:23:02

---

**【问题级别】**

一般

**【描述】**

宏中使用 return、goto、continue、break等改变流程的语句，虽然能简化代码，但同时也隐藏了真实流程，不易于理解，存在过度封装，容易导致资源泄漏等问题。

**【正确示例】**

```
【例外】
用于返回值判断等异常处理场景的宏可以包含改变程序流程的语句。

注意：包含 return、goto、continue、break等改变流程语句的宏命名，务必要体现对应关键字。
比如：

#define RETURN_IF(condition, retValue) \
    if (condition) { \
        RecordFailInfo(__FILE__, __LINE__); \
        return retValue; \
    }

```
**【错误示例】**

```
如下是宏封装 return 容易导致过度封装和使用的场景：

如下代码，status的判断是主干流程的一部分，用宏封装起来后，变得不直观了，阅读时习惯性把RETURN_IF宏忽略掉了，从而导致对主干流程的理解有偏差。

#define LOG_AND_RETURN_IF_FAIL(ret, fmt, ...) do { \
    if ((ret) != OK) { \
        (void)ErrLog(fmt, ##__VA_ARGS__); \
        return (ret); \
    } \
} while (0)

#define RETURN_IF(cond, ret) do { \
    if (cond) { \
        return (ret); \
    } \
} while (0)

ret = InitModuleA(a, b, &status);
LOG_AND_RETURN_IF_FAIL(ret, "Init module A failed!"); // 符合

RETURN_IF(status != READY, ERR_NOT_READY); // 不符合： 重要逻辑不明显

ret = InitModuleB(c);
LOG_AND_RETURN_IF_FAIL(ret, "Init module B failed!"); // 符合
如下是宏封装 return 也容易引发内存泄漏的场景：

#define CHECK_PTR(ptr, ret) do { \
    if ((ptr) == NULL) { \
        return (ret); \
    } \
} while (0)

...

mem1 = MemAlloc(STR_SIZE_MAX);
CHECK_PTR(mem1, ERR_CODE_XXX);

mem2 = MemAlloc(STR_SIZE_MAX);
CHECK_PTR(mem2, ERR_CODE_XXX); // 内存泄漏问题
如果 mem2 申请内存失败了，CHECK_PTR 会直接返回，而没有释放 mem1。

除此之外，CHECK_PTR 宏命名也不好，宏名只反映了检查动作，没有指明结果。只有看了宏实现才知道指针为空时返回失败。

综上所述：

不推荐宏定义中封装 return、goto、continue、break 等改变程序流程的语句；

```
**【修复建议】**

重构代码逻辑，避免安全隐患
