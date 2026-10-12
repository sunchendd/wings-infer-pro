# G.RES.01-CPP 外部数据作为数组索引或者内存操作长度时，需要校验其合法性

- **规则ID**：71cd759f-a896-49e2-94ae-c36bf2ff703f
- **更新时间**：2025-03-25 19:23:19

---

**【问题级别】**

一般

**【描述】**

当数据作为数组索引访问内存时，必须确保该数据始终在数组的有效范围内。尤其对于来自外部的数据，无论直接或间接作为数组索引，都要对其大小做严格校验。



当数据作为作为内存操作长度时，必须确保该数据始终在内存长度的有效范围内，防止出现内存越界读写风险。如：必须根据目标缓冲区容量的大小限制被复制的数据大小，或者必须确保目标缓冲区容量足够大以容纳要复制的数据。尤其对于来自外部的数据，无论直接或间接作为内存操作长度，都要对其大小做严格校验。

**【正确示例】**

```
如下代码中，修改校验索引的条件，避免差一错误。

struct Dev {
    int id;
    char name[MAX_NAME_LEN];
};

static Dev devs[DEV_NUM];

int SetDevId(size_t index, int id)
{
    if (index >= DEV_NUM) {
        ... // 错误处理  
    }
    devs[index].id = id;
    return 0;
}

如下代码中，对inputTable.count做了校验。

struct ValueTable {  
    size_t count;  
    int val[MAX_NUMBERS];  
};

void ValueTableDup(const ValueTable& inputTable)  
{  
    ValueTable outputTable = {0, {0}};  
    ...

    // 根据业务场景，对来自外部数据的inputTable.count做校验，避免造成缓冲区溢出
    if (inputTable->count >
        sizeof(outputTable.val) / sizeof(outputTable.val[0])) {
        ... // 错误处理
    }

    for (size_t i = 0; i < inputTable.count; i++) {  
        outputTable.val[i] = inputTable.val[i];  
    }  
    ...  
}

```
**【错误示例】**

```
如下代码中，SetDevId函数存在差一错误，当 index 等于 DEV_NUM 时，恰好越界写一个元素。

struct Dev {
    int id;
    char name[MAX_NAME_LEN];
};

static Dev devs[DEV_NUM];

int SetDevId(size_t index, int id)
{
    if (index > DEV_NUM) {         // 存在差一错误
        ... // 错误处理  
    }

    devs[index].id = id;
    return 0;
}

外部输入的数据不一定会直接作为内存复制长度使用，还可能会间接参与内存复制操作。
如下代码中，inputTable.count来自外部数据，虽然没有直接作为内存复制长度使用，而是作为for循环体的上限使用，间接参与了内存复制操作。由于没有校验其大小，可造成缓冲区溢出。

struct ValueTable {  
    size_t count;  
    int val[MAX_NUMBERS];  
};

void ValueTableDup(const ValueTable& inputTable)  
{  
    ValueTable outputTable = {0, {0}};
    ...  
    for (size_t i = 0; i < inputTable.count; i++) {  
        outputTable.val[i] = inputTable.val[i];  
    }  
    ...  
}

```
**【修复建议】**

输入校验包括但不局限于： 校验数据长度校验数据范围校验数据类型和格式校验输入只包含可接受的字符（“白名单”形式），尤其需要注意一些特殊情况下的特殊字符。
