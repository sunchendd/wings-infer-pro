# SecA_CBG_CopyToUserStructInit

- **规则ID**：f242cfda-a6fe-42bd-b296-684e0b5f7958
- **更新时间**：2025-03-25 19:23:33

---

**【问题级别】**

一般

**【描述】**

内核中，在使用copy_to_user向用户态传输数据前，应对传输缓冲区进行初始化，否则将导致内核信息泄露。

**【正确示例】**

```
void good(int a){
 .....
 if(access_ok(a))
  memcmp(..., a, ...); //good, 参数a为入参，使用之前使用access_ok()进行校验
 .....
}

```
**【错误示例】**

```
【Instruction】&nbsp;&nbsp;现有规则HW_CBG_C_COPY_TO_USER_STRUCT_INIT能力：
copy_to_user第2个参数为结构体，检查该结构体是否完全初始化，如果没有，则告警。
覆盖场景：
（1）检查copy_to_user前结构体的每个成员是否全部被赋值，没有则告警；
（2）检查copy_to_user前是否用memset对结构体做过初始化，如有，则不告警；
（3）检查结构体是否在定义时同时初始化，如有，则不告警；
本规则在HW_CBG_C_COPY_TO_USER_STRUCT_INIT基础上进行优化，除原有告警条件外，增加对copy_to_user调用前的每条分支进行检查，若有某分支未完全初始化，则告警。
本规则可以替换HW_CBG_C_COPY_TO_USER_STRUCT_INIT规则。【Example】&nbsp;&nbsp;//good example

struct A
{
 int ma;
 int mb;
};
void test3(void *to,unsigned long n)
{
 struct A a;
 a.ma=100;
 a.mb=100;
 copy_to_user(to,&a,sizeof(a)); //ok
}



//bad example

struct A
{
 int ma;
 int mb;
};

void bad(void *to,unsigned long n)
{
 int num;
 struct A a;
 copy_to_user(to,&a,sizeof(a));//error
}

```
**【修复建议】**

使用copy_to_user前，应对第2个参数变量进行完整的初始化
