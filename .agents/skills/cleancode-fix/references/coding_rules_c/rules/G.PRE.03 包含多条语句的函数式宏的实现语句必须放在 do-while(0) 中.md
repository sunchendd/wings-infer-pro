# G.PRE.03 包含多条语句的函数式宏的实现语句必须放在 do-while(0) 中

- **规则ID**：6be310b8-fc89-4a0c-9b27-eb9b5f08d47e
- **更新时间**：2026-04-07 04:10:02

---

**【问题级别】**

严重

**【描述】**

包含多条语句的函数式宏的实现语句必须放在do-while(0)中。

**【正确示例】**

```
##### 场景1：函数式宏中语句未放在do-while(0)中
- 修复示例：

```c
// 符合
#define FOO(x) \
    do { \
        (void)printf("arg is %d
", (x)); \
        DoSomething((x)); \
    } while (0)
```


```
**【错误示例】**

```
##### 场景1：函数式宏中语句未放在do-while(0)中
- 错误示例：

```cpp
// 不符合
#define FOO(x) \
    (void)printf("arg is %d
", (x)); \
    DoSomething((x));
```

```
**【修复建议】**

将函数式宏中的语句放在do-while(0)中。

推荐使用[Huawei CodeCheck插件](https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305?l=zh-cn)的自动修复/一键格式化功能，详细使用说明见。
