# G.PRE.03-CPP \\#if或\\#elif预处理指令中的常量表达式的值应为布尔值

- **规则ID**：fa6dde1f-1402-4aa5-9a9f-de74fc215cda
- **更新时间**：2025-03-25 19:22:47

---

**【问题级别】**

严重

**【描述】**

#if ... #endif或#if ... #elif ... #endif 的预处理指令中常量表达式的值应为布尔值。

当预处理指令中的常量表达式仅作为开关用途时，不要直接使用0或1，而是使用有意义的标识符来表达确切的含义。

**【正确示例】**

```
#define OLD_VERSION 1000
#define VERSION 3320
#define ENABLE_MMX   1    // 定义开关用途的宏
#define ENABLE_FLOAT 0    // 定义开关用途的宏

#if ENABLE_MMX            // 符合
...
#endif

#if ENABLE_FLOAT          // 符合
...
#endif

#if defined(VERSION)      // 符合
...
#endif

#if VERSION > OLD_VERSION // 符合
...
#endif

```
**【错误示例】**

```
#define VERSION 3320

#if 3320                  // 不符合
...
#endif

#if 0                     // 不符合
...
#endif

#if 1                     // 不符合
...
#endif

#if VERSION               // 不符合
...
#endif

```
**【修复建议】**

使用defined方法判断是否定义标识符，或者使用数值0或1的开关宏
