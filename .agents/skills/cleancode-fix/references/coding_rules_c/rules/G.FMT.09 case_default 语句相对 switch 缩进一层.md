# G.FMT.09 case/default 语句相对 switch 缩进一层

- **规则ID**：06eb243a-2a59-4b84-8d1b-379230c5334b
- **更新时间**：2026-04-07 04:10:04

---

**【问题级别】**

一般

**【描述】**

case/default语句相对switch缩进一层，case中的语句相对case缩进一层。

**【正确示例】**

```
##### 场景1：case/default语句相对switch未缩进一层
- 修复示例：

```c++
switch (var) {
    case CASE1:         // 符合：缩进
        DoSomething1(); // 符合：缩进
        break;
    case CASE2: {       // 符合：带大括号格式
        DoSomething2();
        break;
    }
    ...
    default:
        break;
}
```

```
**【错误示例】**

```
##### 场景1：case/default语句相对switch未缩进一层
- 错误示例：

```c++
switch (var) {
case CASE1:             // 不符合：case 未缩进
    DoSomething1();
    break;
...
default:                // 不符合：default 未缩进
    break;
}
```

```
**【修复建议】**

建议通过格式化工具自动修复。例如[WeCode CodeCheck](https://marketplace.rnd.huawei.com/detail?identifier=wecodeCleanCodeCheck)中的[`FixBot`一键格式化](https://wecode-ex.rnd.huawei.com/Docs/85)。

case/default语句相对switch缩进一层，case中的语句相对case缩进一层。

推荐使用[Huawei CodeCheck插件](https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305?l=zh-cn)的自动修复/一键格式化功能，详细使用说明见。
