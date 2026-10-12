# G.INC.08 禁止在 extern "C" 中包含头文件

- **规则ID**：39be1cf7-86bf-4e91-b768-5a333acae1bd
- **更新时间**：2026-04-07 04:10:02

---

**【问题级别】**

严重

**【描述】**

在 extern "C" 中包含头文件，有可能会导致 extern "C" 嵌套，部分编译器对extern "C" 嵌套层次有限制，嵌套层次太多会编译错误。因此，禁止在 extern "C" 中包含头文件。

**【正确示例】**

```
##### 场景1：extern "C"中包含头文件
- 修复示例：

```cpp
// a.h的内容
...
#ifdef __cplusplus
void Foo(int);
#define A(value) Foo(value)
#else
void A(int);
#endif

// b.h的内容
...
#include "a.h" // 符合

#ifdef __cplusplus
extern "C" {
#endif
void B(void);
#ifdef __cplusplus
}
#endif
```

```
**【错误示例】**

```
##### 场景1：extern "C"中包含头文件
- 错误示例：

```cpp
// a.h的内容
...
#ifdef __cplusplus
void Foo(int);
#define A(value) Foo(value)
#else
void A(int);
#endif

// b.h的内容
...
#ifdef __cplusplus
extern "C" {
#endif
#include "a.h" // 不符合
void B(void);
#ifdef __cplusplus
}
#endif
```

```
**【修复建议】**

修改include位置，不要在extern "C"中include头文件。

推荐使用[Huawei CodeCheck插件](https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305?l=zh-cn)的自动修复/一键格式化功能，详细使用说明见。
