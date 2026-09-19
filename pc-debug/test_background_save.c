/* Regression: background persistence must not depend on menu Save Now. */
#define main embedded_e12_main
#include "test_e12.c"
#undef main
int main(int argc, char **argv) {
    unsigned i;
    (void)argc;
    CHECK(e12_unit_main(1, argv) == 0);
    e12_action = e09_busy = e12_autoload = e12_flush = 0;
    e09_error = 0;
    for (i = 0; i < 16; i++) e12_slots[i].generation = e12_slots[i].saved;
    e12_slots[0].occupied = 1;
    e12_slots[0].id = 0;
    e12_slots[0].source = e11_hash(sources[0], 1024);
    e12_slots[0].sequence = 0;
    memcpy(e12_slots[0].data, sources[0], 1024);
    e12_slots[0].data[64] ^= 0x5a;
    e12_slots[0].generation++;
    /* No menu heartbeat or command: only normal timer/worker state. */
    memset(mailbox, 0, sizeof(mailbox));
    e11_retry = v4_ticks;
    v4_ticks += 499;
    e09_poll();
    CHECK(!e09_busy && e12_dirty() == 1 && !e12_flush);
    v4_ticks++;
    e09_poll();
    CHECK(e09_busy && e11_op == 3 && !e12_flush);
    finish();
    CHECK(e12_dirty() == 0);
    e11_job_slot = 0;
    e11_job_source = e11_hash(sources[0], 1024);
    CHECK(e11_load() == 0);
    CHECK(e11_job[96] == (u8)(sources[0][64] ^ 0x5a));
    puts("PASS: background save without menu/flush and persisted reload");
    return 0;
}
