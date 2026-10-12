# G.FMT.07 函数的返回类型及修饰符与函数名同行

- **规则ID**：39bf6d32-678d-4fd4-b1cb-0abd3919eeb3
- **更新时间**：2026-04-07 04:10:04

---

**【问题级别】**

一般

**【描述】**

函数声明和定义时，函数的返回类型及修饰符和函数名在同一行。

**【正确示例】**

```
##### 场景1：函数返回值类型和函数名不同行
- 修复示例：

```c
static inline int ShortFunc(int a, int b);         // 符合

static inline int LongFuncName(int longParamName1, // 符合
                               int longParamName2,
                               int longParamName3,
                               int longParamName4);
```


```
**【错误示例】**

```
##### 场景1：函数返回值类型和函数名不同行
- 错误示例：

```c
static inline int
ShortFunc(int a, int b);         // 不符合

static inline int
LongFuncName(int longParamName1, // 不符合
             int longParamName2,
             int longParamName3,
             int longParamName4);
```


```
**【修复建议】**

函数声明和定义时，将函数的**返回类型**及**修饰符**和**函数名**放在同一行。

推荐使用[Huawei CodeCheck插件](https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305?l=zh-cn)的自动修复/一键格式化功能，详细使用说明见。
