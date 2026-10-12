# G.CTL.07 switch语句要有default分支

- **规则ID**：3c51f805-41ab-4e80-b703-c5700fb98810
- **更新时间**：2026-04-07 04:10:03

---

**【问题级别】**

严重

**【描述】**

大部分情况下，switch语句中要有default分支，保证在遗漏case标签处理时能够有一个缺省的处理行为。本规范要求统一将default分支放到语句块的最后位置。





**【正确示例】**

```
【例外】

如果switch条件变量是枚举类型，并且 case分支覆盖了所有取值，则可以不要求有default分支。

typedef enum {
    RED,
    GREEN,
    BLUE
} Color;

Color color;
...
// 因为switch条件变量是枚举值，这里可以不用加default处理分支
switch (color) {
    case RED:
        DoRedThing();
        break;
    case GREEN:
        DoGreenThing();
        break;
    case BLUE:
        DoBlueThing();
        ...
        break;
}
现代编译器都具备检查是否在switch语句中遗漏了某些枚举值的case分支的能力，会有相应的warning提示。

```
**【错误示例】**

```
  switch (x) { // 不符合
    case 1:
      break;
    case 2:
      break;
  }


    switch (x) {
        case 1:
            break;
        default: // 不符合
            break;
        case 2:
            break;
    }

```
**【修复建议】**

添加default分支，或者将default分支移到最后
