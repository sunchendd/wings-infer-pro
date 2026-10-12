# G.PRE.09 宏定义不应以分号结尾

- **规则ID**：5376377c-3085-4275-b7d2-f6074e3445af
- **更新时间**：2026-04-07 04:10:03

---

**【问题级别】**

一般

**【描述】**

宏定义不应以分号结尾。

**【正确示例】**

```
##### 场景1：宏定义结尾有分号
- 修复示例：

```c
#define LOOP(count)  for (int i = 0; i < (count); i++) // 符合：删除宏定义结尾分号

int count = ...;
LOOP(5) {
    puts("In a loop
");
}
```


```
**【错误示例】**

```
##### 场景1：宏定义结尾有分号
- 错误示例：

```c
#define LOOP(count)  for (int i = 0; i < (count); i++); // 不符合，结尾有分号

int count = ...;
LOOP(5) { // 宏LOOP定义加分号导致空循环，执行结果不符合预期
    puts("In a loop
");
}
```


```
**【修复建议】**

删除宏定义结尾分号，将是否使用分号的决定权交给宏的使用者。

推荐使用[Huawei CodeCheck插件](https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305?l=zh-cn)的自动修复/一键格式化功能，详细使用说明见。
