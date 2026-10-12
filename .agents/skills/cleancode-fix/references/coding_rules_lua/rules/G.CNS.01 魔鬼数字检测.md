# G.CNS.01 魔鬼数字检测

- **规则ID**：d5c4516a-0345-4ef0-bd6a-7f27e85903f3
- **更新时间**：2026-04-07 04:45:02

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx: 使用了魔鬼数字xxx

**【正确示例】**

```
local millisecond = second * 1000;或者加上注释local millisecond = 1000; -- 1000是毫秒
```
**【错误示例】**
```
local zero = 0
local XX_Timer_INTERVAL_300_MS = 300
```


**【修复建议】**

魔鬼数字即看不懂、难以理解的数字，需要加上注释
