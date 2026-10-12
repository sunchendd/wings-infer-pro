# G.FMT.05 行宽不超过 120 个字符

- **规则ID**：003a6ced-4f74-46f9-a481-2a2ff934aa4c
- **更新时间**：2026-04-07 04:10:04

---

**【问题级别】**

一般

**【描述】**

代码行宽不宜过长，不可以超过120个字符

**【正确示例】**

```
##### 场景1：一行超过120个字符
- 修复示例：

```cpp
void Foo()
{
    int resultFileNumbersX = resultFileNumbers1 + resultFileNumbers2 + resultFileNumbers3 +
        resultFileNumbers4 + resultFileNumbers5 + resultFileNumbers6 + resultFileNumbers7; // 符合，未超过120个字符
    int resultFileNumbersY = resultFileNumbers1 + resultFileNumbers2; // 符合，未超过120个字符
}
```

```
**【错误示例】**

```
##### 场景1：一行超过120个字符
- 错误示例：

```cpp
void Foo()
{
    int resultFileNumbersX = resultFileNumbers1 + resultFileNumbers2 + resultFileNumbers3 + resultFileNumbers4 + resultFileNumbers5 + resultFileNumbers6 + resultFileNumbers7; // 不符合，超过120个字符
    int resultFileNumbersY = resultFileNumbers1 + resultFileNumbers2; // 符合，未超过120个字符
}
```

```
**【修复建议】**

行宽超过120个字符要进行换行，换行请参考[G.FMT.06 换行时将操作符留在行末，新行缩进一层或进行同类对齐]。

推荐使用[Huawei CodeCheck插件](https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305?l=zh-cn)的自动修复/一键格式化功能，详细使用说明见。
