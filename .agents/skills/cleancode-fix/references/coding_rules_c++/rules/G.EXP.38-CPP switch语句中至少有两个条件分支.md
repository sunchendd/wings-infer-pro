# G.EXP.38-CPP switch语句中至少有两个条件分支

- **规则ID**：03467441-d9bc-4680-bfff-2d752c7568f9
- **更新时间**：2025-03-25 19:22:31

---

**【问题级别】**

严重

**【描述】**

单个路径的选择语句更适合用if语句进行判断；且如果条件分支是布尔值，那么也不合适使用switch语句，使用if语句更合适。

**【正确示例】**

```
switch (color) {
    case Color::RED:
        DoRedThing();
        break;
    case Color::GREEN:
        DoGreenThing();
        break;
    case Color::BLUE:
        DoBlueThing();
        break;
    default:                
        DoDefault();
        break;
}

```
**【错误示例】**

```
switch (color) {
    default:         // 不符合：switch是多余的  
        DoDefault();
        break;
}
switch (color) {
    case Color::RED:
    default:         // 不符合：switch是多余的  
        DoDefault();
        break;
}

```
**【修复建议】**

switch至少要有两个分支，单分支的情况可以改为if语句
