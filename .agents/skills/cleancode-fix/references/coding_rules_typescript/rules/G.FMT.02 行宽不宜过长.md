# G.FMT.02 行宽不宜过长

- **规则ID**：faf22f45-b9b3-4353-9b8d-316f0f39779c
- **更新时间**：2026-04-07 04:35:00

---

**【问题级别】**

提示

**【描述】**

代码行宽不宜过长，否则不利于阅读。建议每行字符数不要超过 160个；除非超过 160 能显著增加可读性，并且不会隐藏信息。

**【正确示例】**

```
##### 场景1：行宽
- 修复示例：当行宽超过160个字符时，在合适处换行。

```javascript
let sum = longVaribleName1 + longVaribleName2 + longVaribleName3 +
  longVaribleName4 + longVaribleName5 + longVaribleName6 + longVaribleName7 + longVaribleName8;     

```

```
**【错误示例】**

```
##### 场景1：行宽
- 错误示例：行宽过长。
```javascript
let sum = longVaribleName1 + longVaribleName2 + longVaribleName3 + longVaribleName4 + longVaribleName5 + longVaribleName6 + longVaribleName7 + longVaribleName8;     

```

```
**【修复建议】**

较长的语句、表达式或参数以及注释行（大于160个字符）要进行换行处理。
