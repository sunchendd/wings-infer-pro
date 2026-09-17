#define _GNU_SOURCE

#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <sys/file.h>
#include <sys/stat.h>

#include "alm_intf.h"

/* 产品 Key File 以 XTEA-CTR 密文交付(license.key.enc),对称密钥由构建期
 * (license_sdk/encrypt_key.py)随机生成并编进本二进制(key_material.h,
 * build.sh 生成)。明文只在内存中短暂存在,不落盘、不进交付件。 */
#include "key_material.h"

#ifndef EXPECTED_PRODUCT_NAME
#define EXPECTED_PRODUCT_NAME "KunLun AIPerf SDK"
#endif
#ifndef EXPECTED_PRODUCT_VERSION
#define EXPECTED_PRODUCT_VERSION "26"
#endif
#ifndef DEVICE_CAPACITY_KEY
#define DEVICE_CAPACITY_KEY "LRA4AIPERF01"
#endif
#ifndef DEFAULT_KEY_FILE
#define DEFAULT_KEY_FILE "/opt/wings-license/key/license.key.enc"
#endif
#ifndef HOST_BOARD_SERIAL
#define HOST_BOARD_SERIAL "/host-sys/class/dmi/id/board_serial"
#endif
#ifndef LOCAL_BOARD_SERIAL
#define LOCAL_BOARD_SERIAL "/sys/class/dmi/id/board_serial"
#endif
/* ESN 挂载完整性:目录必须落在真 sysfs 上,防伪 board_serial 目录 bind 进来。 */
#ifndef HOST_DMI_DIR
#define HOST_DMI_DIR "/host-sys/class/dmi/id"
#endif
#ifndef LOCAL_DMI_DIR
#define LOCAL_DMI_DIR "/sys/class/dmi/id"
#endif
#define MOUNTINFO_PATH "/proc/self/mountinfo"
#define MAX_LICENSE_FILE_SIZE (2U * 1024U * 1024U)
#define MAX_KEY_FILE_SIZE 16384U
/* 密文 key 封装格式:"WLC1"(4B magic) + nonce(8B) + XTEA-CTR 密文。 */
#define KEY_BLOB_MAGIC "WLC1"
#define KEY_BLOB_HEADER 12U
#define STATE_FILE_NAME "adaptivelm.state"
#define LOCK_FILE_NAME "checker.lock"
/* 回拨容差:须显著大于复检间隔(watermark = stBaseTime + uiBaseRunMin*60 + elapsed,
 * 两者叠加复检延迟后可能压过 1 天容差,致正常实例误判回拨)。默认 3 天,
 * 可用 --rollback-tolerance-seconds 覆盖。 */
#ifndef SAFETIME_ROLLBACK_TOLERANCE_SECONDS
#define SAFETIME_ROLLBACK_TOLERANCE_SECONDS (3 * 86400)
#endif

static char g_esn[ALM_CONST_ENV_ESN_MAX_LEN + 1];
static char g_state_file[4096];
static pthread_mutex_t g_mutex;
static int g_mutex_initialized;
static pthread_t g_timer_thread;
static pthread_mutex_t g_timer_mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t g_timer_condition = PTHREAD_COND_INITIALIZER;
static int g_timer_running;
static ALM_UINT32 g_timer_cycle_ms;
static ALM_ADAPTER_BASE_TIMER_RUN_FUNC g_timer_callback;
static ALM_VOID *g_timer_data;

static ALM_VOID *alloc_memory(ALM_UINT32 size)
{
    return malloc(size);
}

static ALM_VOID free_memory(ALM_VOID *memory)
{
    free(memory);
}

static ALM_INT32 mutex_create(const ALM_CHAR *name, ALM_UINT32 *id)
{
    (void)name;
    if (id == NULL) {
        return -1;
    }
    /* AdaptiveLM 可能重复创建互斥锁;重复 init 是 UB,懒初始化保护。 */
    if (g_mutex_initialized == 0) {
        if (pthread_mutex_init(&g_mutex, NULL) != 0) {
            return -1;
        }
        g_mutex_initialized = 1;
    }
    *id = 1;
    return ALM_OK;
}

static ALM_INT32 mutex_acquire(ALM_UINT32 id, ALM_UINT32 timeout_ms)
{
    (void)timeout_ms;
    return id == 1 && pthread_mutex_lock(&g_mutex) == 0 ? ALM_OK : -1;
}

static ALM_INT32 mutex_release(ALM_UINT32 id)
{
    return id == 1 && pthread_mutex_unlock(&g_mutex) == 0 ? ALM_OK : -1;
}

static ALM_INT32 mutex_delete(ALM_UINT32 id)
{
    return id == 1 && pthread_mutex_destroy(&g_mutex) == 0 ? ALM_OK : -1;
}

static ALM_INT32 get_system_time(ALM_OS_TIME_STRU *output)
{
    time_t now = time(NULL);
    struct tm current;
    if (output == NULL || now == (time_t)-1 || gmtime_r(&now, &current) == NULL) {
        return -1;
    }
    output->usYear = (ALM_UINT16)(current.tm_year + 1900);
    output->ucMonth = (ALM_UINT8)(current.tm_mon + 1);
    output->ucDay = (ALM_UINT8)current.tm_mday;
    output->ucHour = (ALM_UINT8)current.tm_hour;
    output->ucMinute = (ALM_UINT8)current.tm_min;
    output->ucSecond = (ALM_UINT8)current.tm_sec;
    output->ucReserved = 0;
    return ALM_OK;
}

static ALM_INT32 get_esn_callback(ALM_ENV_ESN_STRU *output)
{
    if (output == NULL || snprintf(output->acEsn, sizeof(output->acEsn), "%s", g_esn) < 0) {
        return -1;
    }
    return ALM_OK;
}

static ALM_INT32 persistence_read(ALM_VOID *buffer, ALM_UINT32 *length, ALM_UINT32 offset)
{
    struct stat info;
    FILE *file;
    size_t read_length;

    if (length == NULL) {
        return -1;
    }
    if (stat(g_state_file, &info) != 0) {
        if (errno == ENOENT) {
            *length = 0;
            return ALM_OK;
        }
        return -1;
    }
    if (info.st_size < 0 || (uint64_t)info.st_size > UINT32_MAX) {
        return -1;
    }
    if (buffer == NULL || *length == 0) {
        *length = (ALM_UINT32)info.st_size;
        return ALM_OK;
    }
    if ((uint64_t)offset + *length > (uint64_t)info.st_size) {
        return -1;
    }
    file = fopen(g_state_file, "rb");
    if (file == NULL || fseek(file, (long)offset, SEEK_SET) != 0) {
        if (file != NULL) fclose(file);
        return -1;
    }
    read_length = fread(buffer, 1, *length, file);
    fclose(file);
    return read_length == *length ? ALM_OK : -1;
}

static ALM_INT32 persistence_write(const ALM_VOID *buffer, ALM_UINT32 length, ALM_UINT32 offset)
{
    char temporary[4096];
    FILE *file;
    int directory_fd;
    char *slash;

    if (buffer == NULL || length == 0 || offset != 0 ||
        snprintf(temporary, sizeof(temporary), "%s.tmp.%ld", g_state_file, (long)getpid()) < 0) {
        return -1;
    }
    file = fopen(temporary, "wb");
    if (file == NULL || fwrite(buffer, 1, length, file) != length || fflush(file) != 0 || fsync(fileno(file)) != 0) {
        if (file != NULL) fclose(file);
        unlink(temporary);
        return -1;
    }
    if (chmod(temporary, 0600) != 0) {
        fclose(file);
        unlink(temporary);
        return -1;
    }
    if (fclose(file) != 0 || rename(temporary, g_state_file) != 0) {
        unlink(temporary);
        return -1;
    }
    slash = strrchr(temporary, '/');
    if (slash != NULL) *slash = '\0';
    directory_fd = open(slash != NULL ? temporary : ".", O_RDONLY | O_DIRECTORY);
    if (directory_fd >= 0) {
        (void)fsync(directory_fd);
        close(directory_fd);
    }
    return ALM_OK;
}

static void *timer_main(void *unused)
{
    (void)unused;
    pthread_mutex_lock(&g_timer_mutex);
    while (g_timer_running) {
        struct timespec deadline;
        clock_gettime(CLOCK_REALTIME, &deadline);
        deadline.tv_sec += g_timer_cycle_ms / 1000;
        if (pthread_cond_timedwait(&g_timer_condition, &g_timer_mutex, &deadline) == ETIMEDOUT && g_timer_running) {
            ALM_ADAPTER_BASE_TIMER_RUN_FUNC callback = g_timer_callback;
            ALM_VOID *data = g_timer_data;
            pthread_mutex_unlock(&g_timer_mutex);
            callback(data);
            pthread_mutex_lock(&g_timer_mutex);
        }
    }
    pthread_mutex_unlock(&g_timer_mutex);
    return NULL;
}

static ALM_INT32 timer_start(ALM_UINT32 id, ALM_UINT32 cycle_ms,
    ALM_ADAPTER_BASE_TIMER_RUN_FUNC callback, ALM_VOID *data, ALM_UINT32 *max_lock_ms)
{
    (void)id;
    if (callback == NULL || cycle_ms == 0 || max_lock_ms == NULL) return -1;
    g_timer_cycle_ms = cycle_ms;
    g_timer_callback = callback;
    g_timer_data = data;
    g_timer_running = 1;
    *max_lock_ms = 0;
    return pthread_create(&g_timer_thread, NULL, timer_main, NULL) == 0 ? ALM_OK : -1;
}

static ALM_INT32 timer_stop(ALM_UINT32 id)
{
    (void)id;
    pthread_mutex_lock(&g_timer_mutex);
    g_timer_running = 0;
    pthread_cond_signal(&g_timer_condition);
    pthread_mutex_unlock(&g_timer_mutex);
    return pthread_join(g_timer_thread, NULL) == 0 ? ALM_OK : -1;
}

static int register_adapter_callbacks(void)
{
    /* 一次性注册完整回调集:License 解析与 SafeTime 共用同一套适配器。 */
    ALM_ADAPTER_BASE_FUNCS_STRU callbacks = {0};

    callbacks.fnMemMalloc = alloc_memory;
    callbacks.fnMemFree = free_memory;
    callbacks.fnMutexCreate = mutex_create;
    callbacks.fnMutexAcquire = mutex_acquire;
    callbacks.fnMutexRelease = mutex_release;
    callbacks.fnMutexDel = mutex_delete;
    callbacks.fnTimerStart = timer_start;
    callbacks.fnTimerStop = timer_stop;
    callbacks.fnGetTime = get_system_time;
    callbacks.fnGetEsn = get_esn_callback;
    callbacks.fnPsWrite = persistence_write;
    callbacks.fnPsRead = persistence_read;
    return ALM_AdapterBaseFuncs(&callbacks) == ALM_OK ? 0 : -1;
}

static time_t alm_time_to_epoch(const ALM_OS_TIME_STRU *value)
{
    struct tm parsed = {0};
    parsed.tm_year = value->usYear - 1900;
    parsed.tm_mon = value->ucMonth - 1;
    parsed.tm_mday = value->ucDay;
    parsed.tm_hour = value->ucHour;
    parsed.tm_min = value->ucMinute;
    parsed.tm_sec = value->ucSecond;
    return timegm(&parsed);
}

static int license_time_status_at(
    const char *created_at,
    const char *deadline,
    unsigned int grace_days,
    char grace_until[11],
    time_t current_time);

static int safe_time_validate_license(
    const char *state_dir,
    int initialize_state,
    const char *created_at,
    const char *deadline,
    unsigned int grace_days,
    char grace_until[11],
    unsigned int elapsed_seconds,
    unsigned int rollback_tolerance_seconds)
{
    ALM_START_CFG_STRU start_config = {ALM_CONST_LIC_CBB_C_VER, ALM_TRUE};
    ALM_SAFETIME_STRU safe_time = {0};
    ALM_OS_TIME_STRU current = {0};
    char lock_path[4096];
    char current_text[20];
    struct tm now_tm;
    time_t now;
    time_t watermark;
    time_t effective_time;
    int license_status;
    int lock_fd = -1;
    int started = 0;
    int result = -1;

    if ((mkdir(state_dir, 0700) != 0 && errno != EEXIST) ||
        snprintf(g_state_file, sizeof(g_state_file), "%s/%s", state_dir, STATE_FILE_NAME) < 0 ||
        snprintf(lock_path, sizeof(lock_path), "%s/%s", state_dir, LOCK_FILE_NAME) < 0) {
        return -1;
    }
    lock_fd = open(lock_path, O_CREAT | O_RDWR, 0600);
    if (lock_fd < 0 || flock(lock_fd, LOCK_EX) != 0) goto cleanup;
    if (!initialize_state && access(g_state_file, F_OK) != 0) {
        result = 2;
        goto cleanup;
    }

    /* 回调注册已由 main 统一完成,这里只负责启动 runtime。 */
    if (ALM_Start(&start_config) != ALM_OK) goto cleanup;
    started = 1;
    if (ALM_SafeTimeGetBaseInfo(&safe_time) != ALM_OK || get_system_time(&current) != ALM_OK) goto cleanup;

    now = alm_time_to_epoch(&current);
    watermark = alm_time_to_epoch(&safe_time.stBaseTime);
    if (now == (time_t)-1 || watermark == (time_t)-1) goto cleanup;
    watermark += (time_t)safe_time.uiBaseRunMin * 60;
    watermark += elapsed_seconds;
    if (watermark - now > (time_t)rollback_tolerance_seconds) {
        result = 1;
        goto cleanup;
    }
    effective_time = now > watermark ? now : watermark;
    license_status = license_time_status_at(
        created_at, deadline, grace_days, grace_until, effective_time);
    if (license_status < 0) {
        result = license_status;
        goto cleanup;
    }
    if (gmtime_r(&effective_time, &now_tm) == NULL ||
        strftime(current_text, sizeof(current_text), "%Y-%m-%d %H:%M:%S", &now_tm) == 0 ||
        ALM_SafeTimeSetBaseTime(current_text, safe_time.uiChangeMin) != ALM_OK) {
        goto cleanup;
    }
    result = license_status == 1 ? 3 : 0;

cleanup:
    if (started && ALM_Stop() != ALM_OK) result = -1;
    if (lock_fd >= 0) {
        (void)flock(lock_fd, LOCK_UN);
        close(lock_fd);
    }
    return result;
}

static char *read_file(const char *path, size_t maximum_size, size_t *length)
{
    FILE *file = fopen(path, "rb");
    char *buffer;
    long size;

    if (file == NULL || fseek(file, 0, SEEK_END) != 0) {
        if (file != NULL) {
            fclose(file);
        }
        return NULL;
    }
    size = ftell(file);
    if (size < 0 || (unsigned long)size > maximum_size ||
        (unsigned long)size > UINT32_MAX || fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        return NULL;
    }
    buffer = calloc((size_t)size + 1, 1);
    if (buffer == NULL || fread(buffer, 1, (size_t)size, file) != (size_t)size) {
        free(buffer);
        fclose(file);
        return NULL;
    }
    fclose(file);
    *length = (size_t)size;
    return buffer;
}

static uint32_t load_be32(const unsigned char *bytes)
{
    return ((uint32_t)bytes[0] << 24) | ((uint32_t)bytes[1] << 16) |
           ((uint32_t)bytes[2] << 8) | (uint32_t)bytes[3];
}

static void store_be32(unsigned char *bytes, uint32_t value)
{
    bytes[0] = (unsigned char)(value >> 24);
    bytes[1] = (unsigned char)(value >> 16);
    bytes[2] = (unsigned char)(value >> 8);
    bytes[3] = (unsigned char)value;
}

/* XTEA 32 轮加密单个 64bit block,与 encrypt_key.py 的实现严格等价。 */
static void xtea_encrypt_block(const uint32_t key_words[4], uint32_t *v0, uint32_t *v1)
{
    uint32_t sum = 0;
    unsigned int round;

    for (round = 0; round < 32; ++round) {
        *v0 += ((((*v1 << 4) ^ (*v1 >> 5)) + *v1) ^ (sum + key_words[sum & 3]));
        sum += 0x9E3779B9U;
        *v1 += ((((*v0 << 4) ^ (*v0 >> 5)) + *v0) ^ (sum + key_words[(sum >> 11) & 3]));
    }
}

/* 解密 license.key.enc(magic + nonce + XTEA-CTR 密文)。
 * 输出为 malloc 缓冲(*out/*out_len),调用方负责 free;格式错误返回 -1。 */
static int decrypt_key_blob(
    const unsigned char *blob,
    size_t blob_len,
    unsigned char **out,
    size_t *out_len)
{
    uint32_t key_words[4];
    uint32_t counter_hi;
    uint32_t counter_lo;
    unsigned char *plain;
    size_t cipher_len;
    size_t offset;
    unsigned int index;

    if (blob_len < KEY_BLOB_HEADER || memcmp(blob, KEY_BLOB_MAGIC, 4) != 0) {
        return -1;
    }
    counter_hi = load_be32(blob + 4);
    counter_lo = load_be32(blob + 8);
    for (index = 0; index < 4; ++index) {
        key_words[index] = load_be32(KEY_WRAP_KEY + index * 4);
    }
    cipher_len = blob_len - KEY_BLOB_HEADER;
    plain = (unsigned char *)malloc(cipher_len > 0 ? cipher_len : 1);
    if (plain == NULL) {
        return -1;
    }
    for (offset = 0; offset < cipher_len; offset += 8) {
        unsigned char stream[8];
        uint32_t v0 = counter_hi;
        uint32_t v1 = counter_lo;
        size_t chunk = cipher_len - offset < 8 ? cipher_len - offset : 8;
        size_t byte_index;

        xtea_encrypt_block(key_words, &v0, &v1);
        store_be32(stream, v0);
        store_be32(stream + 4, v1);
        for (byte_index = 0; byte_index < chunk; ++byte_index) {
            plain[offset + byte_index] =
                blob[KEY_BLOB_HEADER + offset + byte_index] ^ stream[byte_index];
        }
        if (++counter_lo == 0) {
            ++counter_hi;
        }
    }
    *out = plain;
    *out_len = cipher_len;
    return 0;
}

static int normalize_esn(char *value)
{
    char *source = value;
    char *target = value;
    char *end;
    size_t length;

    while (isspace((unsigned char)*source)) {
        ++source;
    }
    end = source + strlen(source);
    while (end > source && isspace((unsigned char)end[-1])) {
        --end;
    }
    while (source < end) {
        if (!isalnum((unsigned char)*source)) {
            return -1;
        }
        *target++ = (char)toupper((unsigned char)*source);
        ++source;
    }
    *target = '\0';
    length = strlen(value);
    return length > 0 && length <= 40 ? 0 : -1;
}

static int read_board_esn(char *buffer, size_t size)
{
    const char *paths[] = {HOST_BOARD_SERIAL, LOCAL_BOARD_SERIAL};
    size_t index;

    for (index = 0; index < sizeof(paths) / sizeof(paths[0]); ++index) {
        FILE *file = fopen(paths[index], "r");
        if (file == NULL) {
            continue;
        }
        if (fgets(buffer, (int)size, file) != NULL) {
            fclose(file);
            return normalize_esn(buffer);
        }
        fclose(file);
    }
    return -1;
}

/* mountinfo 行: "36 35 0:34 / /sys rw,... - sysfs sysfs rw",
 * mount point 为第 5 字段(空格转义为 \040),fstype 紧跟 "-" 之后。
 *
 * 覆盖关系是"挂载点是目标路径的祖先":对每个目标路径取最长前缀挂载点
 * (最内层),要求其 fstype 为 sysfs。方向不能反——标准容器里
 * /sys/class/dmi/id 不是独立挂载点(被整树 /sys sysfs 挂载覆盖,本身还
 * 是符号链接),要求"挂载点在目标之下"会恒落空;祖先方向上 "/" 必然
 * 存在,匹配必然终止,fstype 判定恒可做出。Docker 对符号链接路径的 bind
 * 会被内核规范化为真实路径(/sys/devices/virtual/dmi/id),故本地组同时
 * 接受 class 与 devices 两种拼写,任一覆盖挂载为 sysfs 即通过。防伪语义
 * 不放松:伪造目录 bind(tmpfs/ext4)或单文件 bind 恰是更长的祖先匹配,
 * fstype 不是 sysfs,直接拦下。 */
static int mount_covers_target(const char *mount_point, size_t length, const char *target)
{
    size_t target_length = strlen(target);

    if (strncmp(target, mount_point, length) != 0) {
        return 0;
    }
    return target_length == length || target[length] == '/';
}

static int dmi_mounts_are_sysfs(void)
{
    /* 判定对象是 read_board_esn 实际可能读到的每条路径,全取 AND:
     * host bind 的 class 拼写,以及本地 class 拼写与其符号链接解析目标
     * (devices 拼写)。任何一条读路径可被非 sysfs 挂载顶替都是防伪漏洞,
     * 故不做"组内任一通过"的宽松判定。 */
    static const char *const targets[] = {
        "/host-sys/class/dmi/id/board_serial",
        "/sys/class/dmi/id/board_serial",
        "/sys/devices/virtual/dmi/id/board_serial",
    };
    const size_t target_count = sizeof(targets) / sizeof(targets[0]);
    char fstypes[3][32];
    size_t matched[3];
    FILE *file;
    char line[4096];
    size_t index;

    for (index = 0; index < target_count; ++index) {
        fstypes[index][0] = '\0';
        matched[index] = 0;
    }
    file = fopen(MOUNTINFO_PATH, "r");
    if (file == NULL) {
        return -1;
    }
    while (fgets(line, sizeof(line), file) != NULL) {
        char *separator = strstr(line, " - ");
        char *mount_point;
        char *fstype;
        char *end;
        size_t length;
        size_t fields;

        if (separator == NULL) {
            continue;
        }
        *separator = '\0';
        fstype = separator + 3;
        mount_point = NULL;
        fields = 0;
        end = line;
        while (end != NULL && fields < 5) {
            char *field = end;
            end = strchr(end, ' ');
            if (end != NULL) {
                *end = '\0';
                ++end;
            }
            if (fields == 4) {
                mount_point = field;
            }
            ++fields;
        }
        if (mount_point == NULL || fields != 5) {
            continue;
        }
        end = strchr(fstype, ' ');
        if (end != NULL) {
            *end = '\0';
        }
        length = strlen(mount_point);
        for (index = 0; index < target_count; ++index) {
            /* 等长后行覆盖前行:同路径 overmount 时 mount ID 大者在顶层。 */
            if (mount_covers_target(mount_point, length, targets[index]) &&
                length >= matched[index]) {
                matched[index] = length;
                snprintf(fstypes[index], sizeof(fstypes[index]), "%s", fstype);
            }
        }
    }
    fclose(file);
    /* 每条读路径的最长祖先挂载都必须是 sysfs;任一缺失或非 sysfs 即拒。 */
    for (index = 0; index < target_count; ++index) {
        if (matched[index] == 0 || strcmp(fstypes[index], "sysfs") != 0) {
            return -1;
        }
    }
    return 0;
}

static int parse_date(const char *value, struct tm *parsed)
{
    char *end;

    memset(parsed, 0, sizeof(*parsed));
    end = strptime(value, "%Y-%m-%d", parsed);
    return end != NULL && (*end == '\0' || *end == ' ');
}

/* License 字段拼入 JSON 前必须转义,否则畸形但验签通过的字段会产出非法 JSON。 */
static char *json_escape(const char *value)
{
    size_t length = strlen(value);
    size_t index;
    char *escaped;
    char *target;

    escaped = malloc(length * 6 + 1);
    if (escaped == NULL) {
        return NULL;
    }
    target = escaped;
    for (index = 0; index < length; ++index) {
        unsigned char current = (unsigned char)value[index];
        if (current == '"' || current == '\\') {
            *target++ = '\\';
            *target++ = (char)current;
        } else if (current < 0x20) {
            target += sprintf(target, "\\u%04x", (unsigned int)current);
        } else {
            *target++ = (char)current;
        }
    }
    *target = '\0';
    return escaped;
}

static int license_time_status_at(
    const char *created_at,
    const char *deadline,
    unsigned int grace_days,
    char grace_until[11],
    time_t now)
{
    char today[11];
    time_t deadline_time;
    struct tm current;
    struct tm parsed_deadline;

    if (now == (time_t)-1 || gmtime_r(&now, &current) == NULL ||
        strftime(today, sizeof(today), "%Y-%m-%d", &current) == 0) {
        return -1;
    }
    /* created_at 必须先通过格式校验:空串/畸形格式在 strncmp 下会被静默放行。 */
    if (!parse_date(created_at, &(struct tm){0})) {
        return -1;
    }
    if (strncmp(today, created_at, 10) < 0) return -2;
    if (strcmp(deadline, "PERMANENT") == 0) {
        strcpy(grace_until, deadline);
        return 0;
    }
    if (!parse_date(deadline, &parsed_deadline)) {
        return -1;
    }
    deadline_time = timegm(&parsed_deadline);
    if (deadline_time == (time_t)-1 ||
        gmtime_r(&(time_t){deadline_time + (time_t)grace_days * 86400}, &parsed_deadline) == NULL ||
        strftime(grace_until, 11, "%Y-%m-%d", &parsed_deadline) == 0) {
        return -1;
    }
    if (strcmp(today, deadline) <= 0) {
        return 0;
    }
    return strcmp(today, grace_until) <= 0 ? 1 : -3;
}

int main(int argc, char **argv)
{
    ALM_LIC_STORE_STRU license_store;
    ALM_LIC_STORE_BBOM_STRU *capacity = NULL;
    char board_esn[65] = {0};
    char grace_until[11] = {0};
    char *license = NULL;
    char *key = NULL;
    size_t license_length = 0;
    size_t key_length = 0;
    const char *license_path = NULL;
    const char *state_dir = NULL;
    int initialize_state = 0;
    long long used_devices = -1;
    long long request_devices = -1;
    unsigned int elapsed_seconds = 0;
    unsigned int rollback_tolerance_seconds = SAFETIME_ROLLBACK_TOLERANCE_SECONDS;
    unsigned int index;
    unsigned int capacity_matches = 0;
    int time_status;
    int result;

    for (index = 1; index < (unsigned int)argc;) {
        if (strcmp(argv[index], "--initialize-state") == 0) {
            initialize_state = 1;
            ++index;
            continue;
        }
        if (index + 1 >= (unsigned int)argc) {
            fprintf(stderr, "missing value for argument: %s\n", argv[index]);
            return 2;
        }
        if (strcmp(argv[index], "--license-file") == 0) {
            if (license_path != NULL) return 2;
            license_path = argv[index + 1];
        } else if (strcmp(argv[index], "--state-dir") == 0) {
            if (state_dir != NULL) return 2;
            state_dir = argv[index + 1];
        } else if (strcmp(argv[index], "--elapsed-seconds") == 0) {
            char *end = NULL;
            unsigned long parsed = strtoul(argv[index + 1], &end, 10);
            if (end == argv[index + 1] || *end != '\0' || parsed > UINT32_MAX) return 2;
            elapsed_seconds = (unsigned int)parsed;
        } else if (strcmp(argv[index], "--used-devices") == 0) {
            char *end = NULL;
            long long parsed = strtoll(argv[index + 1], &end, 10);
            if (end == argv[index + 1] || *end != '\0' || parsed < 0) return 2;
            used_devices = parsed;
        } else if (strcmp(argv[index], "--request-devices") == 0) {
            char *end = NULL;
            long long parsed = strtoll(argv[index + 1], &end, 10);
            if (end == argv[index + 1] || *end != '\0' || parsed < 0) return 2;
            request_devices = parsed;
        } else if (strcmp(argv[index], "--rollback-tolerance-seconds") == 0) {
            char *end = NULL;
            unsigned long parsed = strtoul(argv[index + 1], &end, 10);
            if (end == argv[index + 1] || *end != '\0' || parsed > UINT32_MAX) return 2;
            rollback_tolerance_seconds = (unsigned int)parsed;
        } else {
            fprintf(stderr, "unknown argument: %s\n", argv[index]);
            return 2;
        }
        index += 2;
    }
    if (license_path == NULL || state_dir == NULL) {
        fprintf(stderr,
            "usage: %s --license-file PATH --state-dir PATH [--initialize-state] "
            "[--used-devices N --request-devices N] "
            "[--elapsed-seconds N] [--rollback-tolerance-seconds N]\n",
            argv[0]);
        return 2;
    }
    if ((used_devices >= 0) != (request_devices >= 0)) {
        fprintf(stderr, "--used-devices and --request-devices must be given together\n");
        return 2;
    }

    if (dmi_mounts_are_sysfs() != 0) {
        fprintf(stderr, "board serial mount is not a real sysfs mount\n");
        return 3;
    }
    if (read_board_esn(board_esn, sizeof(board_esn)) != 0) {
        fprintf(stderr, "failed to read a valid board serial\n");
        return 3;
    }
    if (snprintf(g_esn, sizeof(g_esn), "%s", board_esn) < 0) {
        fprintf(stderr, "failed to initialize ESN callback\n");
        return 3;
    }
    license = read_file(license_path, MAX_LICENSE_FILE_SIZE, &license_length);
    key = read_file(DEFAULT_KEY_FILE, MAX_KEY_FILE_SIZE, &key_length);
    if (license == NULL || key == NULL) {
        fprintf(stderr, "failed to read License or Key File\n");
        free(license);
        free(key);
        return 4;
    }
    {
        unsigned char *key_plain = NULL;
        size_t key_plain_length = 0;
        if (decrypt_key_blob((const unsigned char *)key, key_length, &key_plain, &key_plain_length) != 0) {
            fprintf(stderr, "key file decryption failed\n");
            free(license);
            free(key);
            return 4;
        }
        free(key);
        key = (char *)key_plain;
        key_length = key_plain_length;
    }

    /* 统一注册一次完整回调集(parser 与 SafeTime 共用),消除二次覆盖注册。 */
    if (register_adapter_callbacks() != 0) {
        fprintf(stderr, "AdaptiveLM callback registration failed\n");
        free(license);
        free(key);
        return 5;
    }

    ALM_StInitLicStore(&license_store);
    result = ALM_LicParser(
        license,
        (ALM_UINT32)license_length,
        key,
        (ALM_UINT32)key_length,
        &license_store);
    free(license);
    free(key);
    if (result != ALM_OK) {
        fprintf(stderr, "AdaptiveLM License validation failed: 0x%08X\n", (unsigned int)result);
        ALM_StClsLicStore(&license_store);
        return 6;
    }

    if (strcmp(license_store.stGeneralInfo.acFilePrdName, EXPECTED_PRODUCT_NAME) != 0 ||
        strcmp(license_store.stGeneralInfo.acFilePrdVer, EXPECTED_PRODUCT_VERSION) != 0) {
        fprintf(stderr, "License product or version mismatch\n");
        ALM_StClsLicStore(&license_store);
        return 7;
    }
    if (license_store.stGeneralInfo.eLicType != ALM_LIC_TYPE_COMM ||
        license_store.stAddtion.eLkLockModel != ALM_LIC_LK_LOCKMODEL_NODELOCK) {
        fprintf(stderr, "License type or lock model mismatch\n");
        ALM_StClsLicStore(&license_store);
        return 7;
    }
    if (license_store.stGeneralInfo.stEsns.uiNum != 1 ||
        strcmp(license_store.stGeneralInfo.stEsns.pstArray[0].acEsn, board_esn) != 0) {
        fprintf(stderr, "License ESN does not match board serial\n");
        ALM_StClsLicStore(&license_store);
        return 8;
    }

    for (index = 0; index < license_store.stBbomInfo.uiNum; ++index) {
        ALM_LIC_STORE_BBOM_STRU *candidate = &license_store.stBbomInfo.pstArray[index];
        if (candidate->pcBBomName != NULL && strcmp(candidate->pcBBomName, DEVICE_CAPACITY_KEY) == 0) {
            if (candidate->eType != ALM_LIC_BBOM_RESOURCE) {
                fprintf(stderr, "capacity key is not a resource item\n");
                ALM_StClsLicStore(&license_store);
                return 9;
            }
            capacity = candidate;
            ++capacity_matches;
        }
    }
    if (capacity == NULL || capacity_matches != 1) {
        fprintf(stderr, "required capacity key must occur exactly once\n");
        ALM_StClsLicStore(&license_store);
        return 9;
    }
    time_status = safe_time_validate_license(
        state_dir,
        initialize_state,
        license_store.stAddtion.acFileCreateTime,
        capacity->stTimeInfo.stValid.acDeadLine,
        capacity->stTimeInfo.uiGraceDays,
        grace_until,
        elapsed_seconds,
        rollback_tolerance_seconds);
    if (time_status != 0 && time_status != 3) {
        if (time_status == 1) {
            fprintf(stderr, "system clock rollback detected\n");
        } else if (time_status == 2) {
            fprintf(stderr, "AdaptiveLM SafeTime state is missing\n");
        } else if (time_status == -2) {
            fprintf(stderr, "License is not yet valid\n");
        } else if (time_status == -3) {
            fprintf(stderr, "License is expired\n");
        } else {
            fprintf(stderr, "AdaptiveLM SafeTime failure\n");
        }
        ALM_StClsLicStore(&license_store);
        if (time_status == -2) return 12;
        if (time_status == -3) return 10;
        return 11;
    }

    /* 容量配额在 C 内比较:used/request 由编排层传入,授权数直接取自验签后的
     * 证书内容,比较结果不依赖任何可被替换的脚本/环境变量。 */
    if (used_devices >= 0 &&
        used_devices + request_devices > (long long)capacity->ulValue) {
        printf(
            "{\"status\":\"capacity_exceeded\",\"authorized_device_count\":%lu,"
            "\"used_device_count\":%lld,\"request_device_count\":%lld,"
            "\"reason\":\"used plus requested devices exceed authorized capacity\"}\n",
            (unsigned long)capacity->ulValue,
            used_devices,
            request_devices);
        ALM_StClsLicStore(&license_store);
        return 15;
    }

    {
        char *escaped_lsn = json_escape(license_store.stGeneralInfo.acLsn);
        char *escaped_product = json_escape(license_store.stGeneralInfo.acFilePrdName);
        char *escaped_version = json_escape(license_store.stGeneralInfo.acFilePrdVer);
        char *escaped_created = json_escape(license_store.stAddtion.acFileCreateTime);
        char *escaped_deadline = json_escape(capacity->stTimeInfo.stValid.acDeadLine);
        char *escaped_grace = json_escape(grace_until);
        int output_ok = escaped_lsn != NULL && escaped_product != NULL &&
            escaped_version != NULL && escaped_created != NULL &&
            escaped_deadline != NULL && escaped_grace != NULL;

        if (output_ok) {
            printf(
                "{\"status\":\"%s\",\"license_id\":\"%s\","
                "\"product_name\":\"%s\",\"product_version\":\"%s\","
                "\"capacity_key\":\"%s\",\"valid_from\":\"%s\","
                "\"valid_until\":\"%s\",\"grace_until\":\"%s\","
                "\"authorized_device_count\":%lu,\"reason\":%s}\n",
                time_status == 0 ? "valid" : "grace",
                escaped_lsn,
                escaped_product,
                escaped_version,
                DEVICE_CAPACITY_KEY,
                escaped_created,
                escaped_deadline,
                escaped_grace,
                (unsigned long)capacity->ulValue,
                time_status == 0 ? "null" : "\"License is within its grace period\"");
        }
        free(escaped_lsn);
        free(escaped_product);
        free(escaped_version);
        free(escaped_created);
        free(escaped_deadline);
        free(escaped_grace);
        ALM_StClsLicStore(&license_store);
        if (!output_ok) {
            return 4;
        }
    }
    return 0;
}
