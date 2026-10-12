# SecA_WMP_ArrayOverStep

- **规则ID**：baff87fb-bf4c-42b7-953a-03f0cc9312cc
- **更新时间**：2026-04-07 04:10:01

---

**【问题级别】**

一般

**【描述】**

检查数组下标越界导致的缓冲区溢出问题

**【正确示例】**

```
```c
//good example

#define CONST_NUM 24
#define MAX_SIZE 16

typedef struct {
 int len;
 char *p;
 char pArr[MAX_SIZE];
}MsgInfo;

int getIndex();
void useData(int len);

/==================== good case ====================
// 取余结果经过校验作为数组下标
void test_good01(int a)
{
 int arr[MAX_SIZE] = {0};
 int index = a % CONST_NUM;
 
 if (index < MAX_SIZE) {
  arr[index] = 10; // ok
 }
}

// 函数返回值经过校验作为数组下标
void test_good02(int a)
{
 int arr[MAX_SIZE] = {0};
 int index = 0;
 index = getIndex();
 
 if (index < MAX_SIZE) {
  arr[index] = 10;  // ok
 }
 else {
  arr[index] = 10; // ok
 }
}

// 结构体
void test_good03(MsgInfo *msg, int inputLen)
{
 int arr[MAX_SIZE] = {0};
 msg->len = inputLen % CONST_NUM;
 
 if (msg->len >= MAX_SIZE) {
  return;
 }
 
 useData(arr[msg->len]);  // ok
}
```

```
**【错误示例】**

```
```c
//bad example

#define CONST_NUM 24
#define MAX_SIZE 16

typedef struct {
 int len;
 char *p;
 char pArr[MAX_SIZE];
}MsgInfo;

int getIndex();
void useData(int len);

//==================== bad case ====================
// 取余结果未经校验作为数组下标
void test_bad01(int a)
{
 int index = (a % CONST_NUM);
 int arr[MAX_SIZE] = {0};
 
 int jIndex;
 jIndex = index % MAX_SIZE;
 
 arr[index] = 10;  // error
 useData(arr[jIndex]); // ok
 
 int bbb = a;
 useData(arr[bbb]); // ok
}

// 函数返回值未经校验作为数组下标
void test_bad02(int a)
{
 int arr[MAX_SIZE] = {0};
 int index, len1;
 index = getIndex();
 
 useData(arr[index]);  // error
}

// 结构体
void test_bad03(MsgInfo *msg, int inputLen)
{
 int arr[MAX_SIZE] = {0};
 msg->len = inputLen % CONST_NUM;
 useData(arr[msg->len]);  // error
}

// 结构体
void test_bad04(MsgInfo *msg, int inputLen)
{
 int arr[MAX_SIZE] = {0};
 int idx = inputLen % CONST_NUM;
 useData(msg->pArr[idx]);  // error
}
```

```
**【修复建议】**

使用数组时，要判断下标是否超出范围
