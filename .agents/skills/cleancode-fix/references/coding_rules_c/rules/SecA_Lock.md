# SecA_Lock

- **规则ID**：a3c157cc-eec5-4ad4-bc7f-b5a06a5f4470
- **更新时间**：2026-04-07 04:10:01

---

**【问题级别】**

严重

**【描述】**

可查找锁/互斥锁已获取但未被释放，或者锁/互斥锁在不使用中间释放的情况下被锁定了两次的很多情况。此类问题通常是由于错误处理路径未能释放锁导致的。结果通常是死锁。

**【正确示例】**

```
```
void TestCaseGood02(bool cond)
{
    pthread_mutex_t mutexLocal;
    pthread_mutex_init(&mutexLocal, 0);
    for (int i = 0; i < 11; i++)  {
        pthread_mutex_lock(&mutexLocal);
        /* 符合: */
        pthread_mutex_unlock(&mutexLocal);
    }
}
```

```
**【错误示例】**

```
```
    void test3(){
        pthread_mutex_t mutex;
        pthread_mutex_t condition;
        pthread_mutex_wait(&condition, &mutex); // => infer mutex is locked upon return
        pthread_mutex_lock(&mutex); // Defect: double_lock event
    }
```

```
**【修复建议】**

已获取的锁/互斥锁要及时并且正确释放
