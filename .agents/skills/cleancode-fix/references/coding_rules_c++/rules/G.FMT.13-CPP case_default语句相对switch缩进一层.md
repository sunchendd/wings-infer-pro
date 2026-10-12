# G.FMT.13-CPP case/default语句相对switch缩进一层

- **规则ID**：f5548ec3-2efc-4d9e-87bf-03a27fa22581
- **更新时间**：2025-03-25 19:21:55

---

**【问题级别】**

一般

**【描述】**

case/default语句相对switch缩进一层，case中的语句相对case缩进一层。

**【正确示例】**

```
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
**【错误示例】**

```
switch (var) {
case CASE1:             // 不符合：case 未缩进  
    DoSomething1();
    break;
...
default:                // 不符合：default 未缩进  
    break;
}

```
**【修复建议】**

按要求进行缩进
