# G.AST.01 断言必须使用宏定义，且只能在调试版本中生效

- **规则ID**：6502be49-583c-4696-b0cb-9be2a93f7138
- **更新时间**：2026-04-07 04:10:05

---

**【问题级别】**

一般

**【描述】**

C语言标准定义断言为用于诊断测试的宏(assert)，因此，断言只能在调试版本中使用。断言被触发后，程序会立即退出，因此严禁在正式发布版本使用断言，请通过编译选项进行控制。



断言触发时虽然能提供少量提示信息，但这样的提示信息通常只对程序员有用，对用户几乎没有价值。程序总是应该优先考虑从错误中恢复，因此，断言应只在调试阶段作为诊断方式生效，其他时候，断言是一种比注释更好的文档说明。例如，断言可以用来声明使用函数的前提条件。

**【正确示例】**

```
断言必须用宏进行定义，只在调试版本有效，最终发布版本不允许出现assert函数
void good()
{
	int i = 1;
	ASSERT(i > 0);
}

```
**【错误示例】**

```
如下代码示例在发布版本中使用打印替换断言，生成了实际代码，是不正确的设计。

#ifdef DEBUG
#define ASSERT(f)  assert(f)
#else
#define ASSERT(f)  do { \
    if (!(f)) { \
        printf("Error in function=%s, Line=%d
", __FUNCTION__, __LINE__); \
    } \
} while (0)
#endif

```
**【修复建议】**

代码中禁止直接使用系统函数assert。断言必须用宏进行定义，只在调试版本有效，最终发布版本不允许出现assert函数。

例如可以按下面的代码实现：



#include <assert.h>

#ifdef DEBUG

#define ASSERT(f) assert(f)

#else

#define ASSERT(f) ((void)0)

#endif



在linux内核中定义ASSERT宏，可以采用如下方式：

#ifdef DEBUG

#define ASSERT(f) BUG_ON(!(f))

#else

#define ASSERT(f) ((void)0)

#endif



不用作断言的宏，其名字中不应包含ASSERT，以避免引起混淆。
