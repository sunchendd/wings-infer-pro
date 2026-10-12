# G.PRE.11 #if或#elif预处理指令中的常量表达式的值应为布尔值

- **规则ID**：a9e4dc83-b73b-469d-a0a3-1f0d34a29ac0
- **更新时间**：2026-04-07 04:10:03

---

**【问题级别】**

严重

**【描述】**

`#if ... #endif`或`#if ... #elif ... #endif`的预处理指令中常量表达式的值应为布尔值。

**【正确示例】**

```
##### 场景1：使用数值0或1的开关宏
- 修复示例：将`0`或`1`定义为有意义的标识符，并在`#if ... #endif`或`#if ... #elif ... #endif`中使用。

```c
#define ENABLE_MMX   1
#define ENABLE_FLOAT 0


#if ENABLE_MMX            // 符合：使用已定义的有意义的标识符
...
#endif

#if ENABLE_FLOAT          // 符合：使用已定义的有意义的标识符
...
#endif
```
##### 场景2：`#if`或`#elif`中常量表达式的值不为布尔值
- 修复示例：

```c
#define OLD_VERSION 1000
#define VERSION 3320

#if defined(VERSION)      // 符合
...
#endif

#if VERSION > OLD_VERSION // 符合
...
#endif
```


```
**【错误示例】**

```
##### 场景1：使用数值0或1的开关宏
- 错误示例：

```c
#if 0       // 不符合
...
#endif

#if 1       // 不符合
...
#endif
```
##### 场景2：`#if`或`#elif`中常量表达式的值不为布尔值
- 错误示例：

```c
#define VERSION 3320

#if 3320    // 不符合：非布尔值，3320是整型值
...
#endif

#if VERSION // 不符合：非布尔值，VERSION是整型值
...
#endif
```


```
**【修复建议】**

1. 当预处理指令中的常量表达式仅作为开关用途时，不要直接使用0或1，而是使用有意义的标识符来表达确切的含义。

2. 预处理指令中常量表达式的值应为布尔值，例如使用defined方法（`#if defined(VERSION) `），比较表达式（`#if VERSION > OLD_VERSION`，`#if FUNCNAME == FUNCXXX`）等。
