# G.INT.09 确保枚举常量映射到唯一值

- **规则ID**：8e362a0a-9fed-42f8-baf6-763f3222b09b
- **更新时间**：2026-04-07 04:10:03

---

**【问题级别】**

严重

**【描述】**

同一个枚举类型中的多个枚举常量不应该定义为相同的值。

**【正确示例】**

```
##### 场景1：两个枚举常量为相同值
- 修复示例1：

```c
enum LocalType1 { // 符合：枚举值从0开始，不提供显式的整数赋值
    LOCAL1_TYPE0,
    LOCAL1_TYPE1,
    LOCAL1_TYPE2,
    LOCAL1_TYPE3,
    LOCAL1_TYPE4,
    LOCAL1_TYPE5,
    LOCAL1_TYPE_END
};
```

- 修复示例2：

```c
enum LocalType1 { // 符合：如果第一个枚举值不需要从0开始的话，只对第一个成员赋值，其它成员不提供显示的整数赋值
    LOCAL1_TYPE1 = 1,
    LOCAL1_TYPE2,
    LOCAL1_TYPE3,
    LOCAL1_TYPE4,
    LOCAL1_TYPE5,
    LOCAL1_TYPE_END
};
```

```
**【错误示例】**

```
##### 场景1：两个枚举常量为相同值
- 错误示例：

```c
enum LocalType1 { // 不符合，LOCAL1_TYPE2和LOCAL1_TYPE5值相同，LOCAL1_TYPE3和LOCAL1_TYPE_END值相同
    LOCAL1_TYPE1 = 1,
    LOCAL1_TYPE2,
    LOCAL1_TYPE3,
    LOCAL1_TYPE4 = 1,
    LOCAL1_TYPE5,
    LOCAL1_TYPE_END
};
```

```
**【修复建议】**

1、不提供显式的整数赋值。

2、如果第一个枚举值不需要从0开始的话，只对第一个成员赋值，其它成员不提供显示的整数赋值。

3、如果枚举类型的多个成员确实需要分配相同的值，需要提供显式的整数赋值，并写一条注释，解释为什么这样做。
