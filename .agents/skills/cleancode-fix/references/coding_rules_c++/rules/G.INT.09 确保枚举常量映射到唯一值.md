# G.INT.09 确保枚举常量映射到唯一值

- **规则ID**：c5f783c8-2f75-41f8-8215-0479e9cd9ce6
- **更新时间**：2025-03-25 19:23:06

---

**【问题级别】**

严重

**【描述】**

C语言的枚举类型是具有一组有限值的集合，这些值的标识符被称为枚举常量。枚举常量是一个整数常量表达式，其值可表示为int。尽管C语言允许相同枚举类型中的多个枚举常量具有相同的值，但是人们普遍期望同一个枚举类型中的枚举常量具有不同的值。因此，将同一个枚举类型中的多个枚举常量定义为相同的值可能会导致一些不易被发现的错误。

**【正确示例】**

```
为了防止出现错误代码示例中的问题，枚举类型声明可以采用以下形式之一：

不提供显式的整数赋值，如下示例所示
typedef enum {
    ERR_SYS_ARG_ERR,
    ERR_SYS_SET_ERR,
    ERR_SYS_OCCUPIED_ERR,
    ERR_SYS_REQFREE_ERR,
    ERR_SYS_NO_REC_ERR,
    ERR_SYS_ACTIVED_ERR,
    ERR_SYS_NO_FILE_ERR,
    ERR_SYS_OPEN_ERR,
    ERR_SYS_ASSIGN_ERR,
    ERR_SYS_ALLOC_ERR,
    ERR_SYS_GET_LIST_ERR,
    ERR_SYS_IGNORE_ERR,
    ERR_SYS_REG_ERR,
    ERR_SYS_CALC_ERR,
    ERR_SYS_SNED_ERR,
    ERR_SYS_RECV_ERR,
    ERR_SYS_MODIFY_ERR,
    ERR_SYS_CHECK_ERR,

    ERR_EMG_INVALID_ERR,
    ERR_EMG_TYPE_ERR,
    ...
} SomeModuleErrCodes;
只对第一个成员赋值，如下示例所示
typedef enum {
    ERR_SYS_ARG_ERR      = 0x3a020000,
    ERR_SYS_SET_ERR,
    ERR_SYS_OCCUPIED_ERR,
    ERR_SYS_REQFREE_ERR,
    ERR_SYS_NO_REC_ERR,
    ERR_SYS_ACTIVED_ERR,
    ERR_SYS_NO_FILE_ERR,
    ERR_SYS_OPEN_ERR,
    ERR_SYS_ASSIGN_ERR,
    ERR_SYS_ALLOC_ERR,
    ERR_SYS_GET_LIST_ERR,
    ERR_SYS_IGNORE_ERR,
    ERR_SYS_REG_ERR,
    ERR_SYS_CALC_ERR,
    ERR_SYS_SNED_ERR,
    ERR_SYS_RECV_ERR,
    ERR_SYS_MODIFY_ERR,
    ERR_SYS_CHECK_ERR,

    ERR_EMG_INVALID_ERR,
    ERR_EMG_TYPE_ERR,
    ...
} SomeModuleErrCodes;
在上面的两个选项中，除非第一个枚举数必须具有非零值，否则第一种做法是最简单的方法，因此也是首选方法。

```
**【错误示例】**

```
如下代码示例中，在枚举类型SomeModuleErrCodes中定义错误码的时候，为两个枚举常量分配了显式值，造成 ERR_SYS_MODIFY_ERR 和 ERR_EMG_INVALID_ERR 被隐式声明为相同的值（0x3a020010），对于程序员来说，可能并不明显。
这种定义可能导致的错误是尝试将枚举常量用于 switch 语句的标签。由于 switch 语句中的所有标签都必须是唯一的，因此如下代码违反了此语义约束。

typedef enum {
    ERR_SYS_ARG_ERR = 0x3a020000,
    ERR_SYS_SET_ERR,
    ERR_SYS_OCCUPIED_ERR,
    ERR_SYS_REQFREE_ERR,
    ERR_SYS_NO_REC_ERR,
    ERR_SYS_ACTIVED_ERR,
    ERR_SYS_NO_FILE_ERR,
    ERR_SYS_OPEN_ERR,
    ERR_SYS_ASSIGN_ERR,
    ERR_SYS_ALLOC_ERR,
    ERR_SYS_GET_LIST_ERR,
    ERR_SYS_IGNORE_ERR,
    ERR_SYS_REG_ERR,
    ERR_SYS_CALC_ERR,
    ERR_SYS_SNED_ERR,
    ERR_SYS_RECV_ERR,
    ERR_SYS_MODIFY_ERR,    // 不符合：值与ERR_EMG_INVALID_ERR相同
    ERR_SYS_CHECK_ERR,     // 不符合：值与ERR_EMG_TYPE_ERR相同

    ERR_EMG_INVALID_ERR = 0x3a020010,
    ERR_EMG_TYPE_ERR,
    ...
} SomeModuleErrCodes;

```
**【修复建议】**

（1）纠正编码错误，或者（2）显式指定枚举值
