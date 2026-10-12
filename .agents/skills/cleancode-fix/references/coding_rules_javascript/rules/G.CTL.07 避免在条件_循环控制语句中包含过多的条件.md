# G.CTL.07 避免在条件/循环控制语句中包含过多的条件

- **规则ID**：fc3875de-ee49-47b9-a5af-f75a5b7c9cc8
- **更新时间**：2025-06-05 04:25:02

---

**【问题级别】**

提示

**【描述】**

控制性条件表达式if语句中如果包含过多的条件，会对阅读者造成理解与记忆上的困难，也会在修改时更容易出错。

因此，建议在if语句中的表达式尽量清晰直接，避免陷入具体的条件判断细节。条件判断细节可以在使用if条件判断之前用bool变量代替或封装函数/方法。



if语句中的表达式应清晰直接，并且建议不超过3个，可以根据具体逻辑决定。

**【正确示例】**

```
const isActivityValid = activity.isActive && activity.remaining > 10;
const isUserValid = user.isActive && (user.sex == 'female' || user.level > 3);
// 此处的逻辑应清晰直接，建议在同一抽象层次上，不要陷入细节
if (isActivityValid && isUserValid) { 
  ...
}

```
**【错误示例】**

```
// 此处的逻辑非常多，阅读困难，修改容易出错
if (activity.isActive && activity.remaining > 10 && user.isActive && (user.sex == 'female' || user.level > 3)) {
  ...
}

```
**【修复建议】**

避免在条件/循环控制语句中包含过多的条件
