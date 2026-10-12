# G.CTL.08 switch语句中至少有两个条件分支

- **规则ID**：42d03231-ed57-4a9b-9d56-504d2c2d62e7
- **更新时间**：2026-04-07 04:10:03

---

**【问题级别】**

严重

**【描述】**

switch语句中至少有两个条件分支，否则用if更合适

**【正确示例】**

```
##### 场景1：switch中条件少于两个
- 修复示例：

```c
void Foo(int x, int y)
{
    if (x == 1) { // 符合
        y++;
    }
}
```


```
**【错误示例】**

```
##### 场景1：switch中条件少于两个
- 错误示例：

```c
void Foo(int x, int y)
{
    switch (x) { // 不符合，只有一个case语句
        case 1:
            y++;
            break;
    }
}
```


```
**【修复建议】**

修改为if语句

推荐使用[Huawei CodeCheck插件](https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305?l=zh-cn)的自动修复/一键格式化功能，详细使用说明见。
