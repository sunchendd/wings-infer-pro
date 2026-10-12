# G.CTL.03 避免在条件/循环控制语句中包含过多的条件

- **规则ID**：438639a7-24cb-4192-bf4f-8e4e0928bd8e
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

一般

**【描述】**

控制性条件表达式if语句中如果包含过多的条件，会对阅读者造成理解与记忆上的困难，也会在修改时更容易出错，使代码不易维护，可读性差。因此，避免在条件/循环控制语句中包含过多的条件，建议在if语句中的表达式尽量清晰直接，避免陷入具体的条件判断细节。

**【正确示例】**

```
##### 场景1：if判断语句条件过多
- 修复示例：将if语句判断条件合并，用`bool`变量代替
```python
is_activity_valid = activity.is_active and activity.remaining > 10
is_user_valid = user.is_active and (user.sex == 'female' or user.level > 3)
if is_activity_valid and is_user_valid:  # 符合，此处的逻辑应清晰直接，建议在同一抽象层次上，不要陷入细节
    user.add_coins(1024)
```


```
**【错误示例】**

```
##### 场景1：if判断语句条件过多
- 错误示例：
```python
if activity.is_active and activity.remaining > 10 and \
        user.is_active and (user.sex == 'female' or user.level > 3):  # 不符合，此处的逻辑非常多，阅读困难，修改容易出错
    user.add_coins(1024)
```


```
**【修复建议】**

1. if语句中的表达式应清晰直接，并且建议不超过3个，可以根据具体逻辑决定。

2. 条件判断细节可以在使用`if`条件判断之前用`bool`变量代替或`封装函数/方法`。
