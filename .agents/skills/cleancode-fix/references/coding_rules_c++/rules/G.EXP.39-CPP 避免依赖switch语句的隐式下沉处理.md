# G.EXP.39-CPP 避免依赖switch语句的隐式下沉处理

- **规则ID**：e9412161-24fe-4e71-ae51-49cff8f96171
- **更新时间**：2025-03-25 19:23:17

---

**【问题级别】**

一般

**【描述】**

通常情况下一个非空case语句应该使用break结尾。如果需要做下沉处理，则应该在代码中明确标识出来，提升可读性。

**【正确示例】**

```
switch (color) {
    case Color::RED:
    case Color::GREEN:
    case Color::BLUE:
        DoSomething();        // 符合： 可以针对多个标签执行相同的操作
        break;
    ...
}
switch (color) {
    case Color::ORANGE:
        return Color::YELLOW; // 符合： case标签中使用返回语句
    case Color::CYAN:
        return Color::BLACK;  // 符合： case标签中使用返回语句
    case Color::PURPLE:
        return Color::BLUE;   // 符合： case标签中使用返回语句
    ...
}
从C++17开始可以使用[[fallthrough]]明确标识下沉处理。

switch (color) {
    case Color::RED:
        DoRedThing();
        break;
    case Color::GREEN:
        DoGreenThing();
        [[fallthrough]];      // 符合： 明确标识下沉处理
    case Color::BLUE:
        DoBlueThing();
        break;
    ...
}

```
**【错误示例】**

```
switch (color) {
    case Color::RED:
        DoRedThing();
        break;
    case Color::GREEN:
        DoGreenThing();       // 不符合： 隐式下沉
    case Color::BLUE:
        DoBlueThing();
        break;
    ...
}

```
**【修复建议】**

case语句块确认是否需要break，

1. 如果需要请增加break。

2. 如果不需要应使用下沉标识显式表示出来，如`[[fallthrough]]`(C++17)。
